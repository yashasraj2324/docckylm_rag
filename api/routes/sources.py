import mimetypes
import os
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from ingestion.embedder import get_embedding_model
from pipeline.ingest_worker import (
    process_file_source,
    process_search_results,
    process_web_source,
)
from routes.dependencies import get_db
from vectorstore import qdrant_db
from vectorstore.visual_qdrant import delete_by_source as delete_visual_by_source
from web.loader import fetch_search_results
from cache.redis_client import invalidate_notebook_cache


router = APIRouter(tags=["Sources"])

SUPPORTED_SOURCE_TYPES = {
    ".pdf": ("pdf", "application/pdf"),
    ".doc": ("doc", "application/msword"),
    ".docx": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ".pptx": (
        "pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".webp": ("image", "image/webp"),
}


@router.get("/notebooks/{notebook_id}/sources")
async def list_sources(notebook_id: str):
    """Return all sources for a notebook."""
    return get_db().list_sources(notebook_id)


@router.post("/notebooks/{notebook_id}/sources")
async def add_source(notebook_id: str, file: UploadFile = File(...)):
    """Upload a supported document source and index it in the background."""
    file_name = Path(file.filename or "").name
    extension = Path(file_name).suffix.lower()
    source_info = SUPPORTED_SOURCE_TYPES.get(extension)
    if not file_name or source_info is None:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_TYPES))
        return JSONResponse(
            content={
                "error": f"Unsupported file type. Supported extensions: {supported}"
            },
            status_code=415,
        )

    source_type, default_content_type = source_info
    content_type = mimetypes.guess_type(file_name)[0] or default_content_type
    data = await file.read()
    if not data:
        return JSONResponse(
            content={"error": "Uploaded file is empty"},
            status_code=400,
        )
    db = get_db()
    source_id = db.next_source_id()

    gridfs_file_id = db.upload_source(
        notebook_id, source_id, file_name, data, content_type
    )
    source = db.create_source(
        notebook_id,
        source_id,
        file_name,
        gridfs_file_id,
        "indexing",
        source_type,
        content_type,
    )

    fd, temp_path = tempfile.mkstemp(suffix=extension)
    os.write(fd, data)
    os.close(fd)

    def process():
        embedding_model = get_embedding_model()
        process_file_source(
            db, embedding_model, temp_path, file_name, notebook_id, source_id
        )

    threading.Thread(target=process).start()

    try:
        invalidate_notebook_cache(notebook_id)
    except Exception:
        pass

    return JSONResponse(content=source, status_code=201)


@router.post("/notebooks/{notebook_id}/sources/website")
async def add_website_source(notebook_id: str, request: Request):
    req_data = await request.json()
    if not req_data or "url" not in req_data:
        return JSONResponse(content={"error": "Missing url"}, status_code=400)

    url = req_data["url"]
    db = get_db()
    source_id = db.next_source_id()

    source = db.create_source(
        notebook_id,
        source_id,
        url,
        "web",
        "indexing",
        "website",
        "text/html",
    )

    def process():
        embedding_model = get_embedding_model()
        process_web_source(db, embedding_model, url, notebook_id, source_id)

    threading.Thread(target=process).start()
    return JSONResponse(content=source, status_code=201)


@router.post("/notebooks/{notebook_id}/sources/search")
async def add_search_source(notebook_id: str, request: Request):
    req_data = await request.json()
    if not req_data or "query" not in req_data:
        return JSONResponse(content={"error": "Missing query"}, status_code=400)

    query = req_data["query"]
    db = get_db()

    try:
        results = fetch_search_results(query)
    except Exception as e:
        print(f"Failed to fetch search results: {e}")
        return JSONResponse(content={"error": "Search failed"}, status_code=500)

    if not results:
        return JSONResponse(content={"error": "No results found"}, status_code=404)

    created_sources = []
    for r in results:
        source_id = db.next_source_id()
        source = db.create_source(
            notebook_id,
            source_id,
            r["url"],
            "search",
            "indexing",
            "search",
            "text/html",
        )
        created_sources.append({"source": source, "result_data": r})

    def process(sources_to_process):
        embedding_model = get_embedding_model()
        process_search_results(db, embedding_model, sources_to_process, notebook_id)

    threading.Thread(target=process, args=(created_sources,)).start()

    return JSONResponse(
        content=[item["source"] for item in created_sources], status_code=201
    )


@router.delete("/notebooks/{notebook_id}/sources/{source_id}")
async def delete_source(notebook_id: str, source_id: str):
    """Hard delete a single source from Qdrant, GridFS, and MongoDB."""
    db = get_db()

    sources = db.list_sources(notebook_id)
    target_source = next((s for s in sources if s["id"] == source_id), None)

    try:
        qdrant_db.delete_by_source(source_id)
    except Exception as e:
        print(f"Warning: Failed to delete source from Qdrant: {e}")
    try:
        delete_visual_by_source(source_id)
    except Exception as e:
        print(f"Warning: Failed to delete visual vectors from Qdrant: {e}")

    if target_source and target_source.get("gridfs_file_id"):
        try:
            db.delete_storage_paths([target_source["gridfs_file_id"]])
        except Exception as e:
            print(f"Warning: Failed to delete source from GridFS: {e}")

    db.delete_source_row(source_id)

    try:
        invalidate_notebook_cache(notebook_id)
    except Exception:
        pass

    return {"success": True}


@router.post("/notebooks/{notebook_id}/sources/{source_id}/retry")
async def retry_source(notebook_id: str, source_id: str):
    """Retry ingestion for a failed or stuck source."""
    db = get_db()
    sources = db.list_sources(notebook_id)
    target_source = next((s for s in sources if s["id"] == source_id), None)

    if not target_source:
        return JSONResponse(content={"error": "Source not found"}, status_code=404)

    if target_source.get("status") not in ("failed", "indexing"):
        return JSONResponse(
            content={"error": "Source is not in a retryable state"}, status_code=400
        )

    try:
        qdrant_db.delete_by_source(source_id)
    except Exception as e:
        print(f"Warning: Failed to clean up Qdrant vectors during retry: {e}")
    try:
        delete_visual_by_source(source_id)
    except Exception as e:
        print(f"Warning: Failed to clean up visual vectors during retry: {e}")

    db.update_source_status(source_id, "indexing")

    gridfs_file_id = target_source.get("gridfs_file_id", "")
    file_name = target_source.get("file_name", source_id)

    def process():
        embedding_model = get_embedding_model()

        if gridfs_file_id and gridfs_file_id not in ("web", "search"):
            try:
                file_data = db.download_source_file(gridfs_file_id)
                _, ext = os.path.splitext(file_name)
                fd, temp_path = tempfile.mkstemp(suffix=ext.lower())
                os.write(fd, file_data)
                os.close(fd)

                process_file_source(
                    db, embedding_model, temp_path, file_name, notebook_id, source_id
                )
            except Exception as e:
                print(f"Retry: Failed to re-download source file: {e}")
                db.update_source_status(source_id, "failed")
        else:
            url = file_name
            process_web_source(db, embedding_model, url, notebook_id, source_id)

    threading.Thread(target=process).start()

    return {"success": True, "status": "indexing"}
