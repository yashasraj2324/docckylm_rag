"""
FastAPI application for AI Notebooks.
Replaces the Flask backend with async FastAPI, preserving all routes and
business logic.
"""

import json
import os
import sys
import tempfile
import threading
from uuid import uuid4

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import Database
from ingestion.embedder import get_embedding_model
from llm.chat_model import get_chat_model
from pipeline.flashcards import generate_flashcards
from pipeline.ingest_worker import (
    process_file_source,
    process_search_results,
    process_web_source,
)
from pipeline.naming import generate_notebook_title
from pipeline.query import prepare_answer, stream_answer
from vectorstore import qdrant_db
from web.loader import fetch_search_results
from cache.redis_client import invalidate_notebook_cache

Database().list_notebooks()
print("Connected to MongoDB successfully")

app = FastAPI(title="AI Notebooks API")

# CORS — allow the Next.js dev server (port 3000) and Vercel previews
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

thread_local = threading.local()


def _db():
    if not hasattr(thread_local, "db_instance"):
        thread_local.db_instance = Database()
    return thread_local.db_instance


# ── Health ────────────────────────────────────────────────────────────────────


@app.get("/")
async def python_route():
    return {"message": "Hello from FastAPI!"}


# ── Notebooks ─────────────────────────────────────────────────────────────────


@app.get("/notebooks")
async def list_notebooks():
    """Return all notebooks for the demo user, ordered by most-recently updated."""
    db = _db()
    notebooks = db.list_notebooks()
    return notebooks


@app.post("/notebooks")
async def create_notebook(request: Request):
    """Create a new notebook. Body (JSON): { "title": "..." } (optional)."""
    db = _db()
    body = await request.json()
    title = (body.get("title") or "Untitled notebook").strip()
    notebook = db.create_notebook(title=title)
    return JSONResponse(content=notebook, status_code=201)


@app.delete("/notebooks/{notebook_id}")
async def delete_notebook(notebook_id: str):
    """Hard delete a notebook from MongoDB (DB + GridFS) and Qdrant."""
    db = _db()

    # 1. Delete from Qdrant
    try:
        qdrant_db.delete_by_notebook(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to delete from Qdrant: {e}")

    # 2. Delete from GridFS
    try:
        db.delete_storage_prefix(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to delete from GridFS: {e}")

    # 3. Delete from MongoDB (cascade)
    db.delete_notebook_rows(notebook_id)

    return {"success": True}


@app.post("/notebooks/{notebook_id}/auto-name")
async def auto_name_notebook(notebook_id: str):
    """Generate a dynamic title for the notebook based on its uploaded content."""
    try:
        title = generate_notebook_title(notebook_id)
        db = _db()
        db.rename_notebook(notebook_id, title)
        return {"title": title}
    except Exception as e:
        print(f"Error auto-naming notebook {notebook_id}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── Sources ───────────────────────────────────────────────────────────────────


@app.get("/notebooks/{notebook_id}/sources")
async def list_sources(notebook_id: str):
    """Return all sources for a notebook."""
    db = _db()
    sources = db.list_sources(notebook_id)
    return sources


@app.post("/notebooks/{notebook_id}/sources")
async def add_source(notebook_id: str, file: UploadFile = File(...)):
    """Upload a PDF source."""
    db = _db()
    source_id = db.next_source_id()
    data = await file.read()

    # 1. Upload to GridFS
    gridfs_file_id = db.upload_pdf(notebook_id, source_id, file.filename, data)

    # 2. Create DB row
    source = db.create_source(
        notebook_id, source_id, file.filename, gridfs_file_id, "indexing"
    )

    # 3. Save to temp file and run ingest in the background
    _, ext = os.path.splitext(file.filename or "")
    fd, temp_path = tempfile.mkstemp(suffix=ext.lower())
    os.write(fd, data)
    os.close(fd)

    def process():
        embedding_model = get_embedding_model()
        process_file_source(
            db, embedding_model, temp_path, file.filename, notebook_id, source_id
        )

    threading.Thread(target=process).start()

    # Invalidate cached RAG responses for this notebook
    try:
        invalidate_notebook_cache(notebook_id)
    except Exception:
        pass

    return JSONResponse(content=source, status_code=201)


@app.post("/notebooks/{notebook_id}/sources/website")
async def add_website_source(notebook_id: str, request: Request):
    req_data = await request.json()
    if not req_data or "url" not in req_data:
        return JSONResponse(content={"error": "Missing url"}, status_code=400)

    url = req_data["url"]
    db = _db()
    source_id = db.next_source_id()

    source = db.create_source(notebook_id, source_id, url, "web", "indexing")

    def process():
        embedding_model = get_embedding_model()
        process_web_source(db, embedding_model, url, notebook_id, source_id)

    threading.Thread(target=process).start()
    return JSONResponse(content=source, status_code=201)


@app.post("/notebooks/{notebook_id}/sources/search")
async def add_search_source(notebook_id: str, request: Request):
    req_data = await request.json()
    if not req_data or "query" not in req_data:
        return JSONResponse(content={"error": "Missing query"}, status_code=400)

    query = req_data["query"]
    db = _db()

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
            notebook_id, source_id, r["url"], "search", "indexing"
        )
        created_sources.append({"source": source, "result_data": r})

    def process(sources_to_process):
        embedding_model = get_embedding_model()
        process_search_results(db, embedding_model, sources_to_process, notebook_id)

    threading.Thread(target=process, args=(created_sources,)).start()

    return JSONResponse(
        content=[item["source"] for item in created_sources], status_code=201
    )


@app.delete("/notebooks/{notebook_id}/sources/{source_id}")
async def delete_source(notebook_id: str, source_id: str):
    """Hard delete a single source from Qdrant, GridFS, and MongoDB."""
    db = _db()

    sources = db.list_sources(notebook_id)
    target_source = next((s for s in sources if s["id"] == source_id), None)

    # 1. Delete from Qdrant
    try:
        qdrant_db.delete_by_source(source_id)
    except Exception as e:
        print(f"Warning: Failed to delete source from Qdrant: {e}")

    # 2. Delete from GridFS
    if target_source and target_source.get("gridfs_file_id"):
        try:
            db.delete_storage_paths([target_source["gridfs_file_id"]])
        except Exception as e:
            print(f"Warning: Failed to delete source from GridFS: {e}")

    # 3. Delete from MongoDB
    db.delete_source_row(source_id)

    # Invalidate cached RAG responses
    try:
        invalidate_notebook_cache(notebook_id)
    except Exception:
        pass

    return {"success": True}


@app.post("/notebooks/{notebook_id}/sources/{source_id}/retry")
async def retry_source(notebook_id: str, source_id: str):
    """Retry ingestion for a failed or stuck source."""
    db = _db()
    sources = db.list_sources(notebook_id)
    target_source = next((s for s in sources if s["id"] == source_id), None)

    if not target_source:
        return JSONResponse(content={"error": "Source not found"}, status_code=404)

    if target_source.get("status") not in ("failed", "indexing"):
        return JSONResponse(
            content={"error": "Source is not in a retryable state"}, status_code=400
        )

    # Clean up partial vectors
    try:
        qdrant_db.delete_by_source(source_id)
    except Exception as e:
        print(f"Warning: Failed to clean up Qdrant vectors during retry: {e}")

    db.update_source_status(source_id, "indexing")

    gridfs_file_id = target_source.get("gridfs_file_id", "")
    file_name = target_source.get("file_name", source_id)

    def process():
        embedding_model = get_embedding_model()

        if gridfs_file_id and gridfs_file_id not in ("web", "search"):
            import tempfile

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


# ── Chat ──────────────────────────────────────────────────────────────────────


@app.get("/notebooks/{notebook_id}/messages")
async def list_messages(notebook_id: str):
    """Return full message history for a notebook."""
    db = _db()
    messages = db.list_messages(notebook_id)
    return messages


@app.post("/notebooks/{notebook_id}/chat")
async def chat_stream(notebook_id: str, request: Request):
    """SSE streaming RAG chat endpoint."""
    body = await request.json()
    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse(content={"error": "query is required"}, status_code=400)

    db = _db()

    # Save user message immediately
    try:
        db.save_message(notebook_id, "user", query)
    except Exception as e:
        print(f"Warning: Failed to save user message: {e}")

    # Fetch conversation history
    try:
        history = db.list_messages(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to fetch message history: {e}")
        history = []

    def generate():
        full_answer = []
        citations = []
        try:
            embedding_model = get_embedding_model()
            chat_model = get_chat_model()
            prompt, citations, _ctx, has_context = prepare_answer(
                embedding_model, query, notebook_id, history=history
            )

            if not has_context:
                no_ctx = "I couldn't find relevant information in your sources. Please add PDFs and try again."
                yield f"data: {json.dumps({'type': 'chunk', 'content': no_ctx})}\n\n"
                full_answer.append(no_ctx)
            else:
                for chunk in stream_answer(chat_model, prompt):
                    full_answer.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

        except Exception as e:
            err_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': err_msg})}\n\n"
            full_answer.append(err_msg)

        finally:
            answer_text = "".join(full_answer)
            if answer_text:
                try:
                    db.save_message(notebook_id, "assistant", answer_text, citations)
                except Exception as e:
                    print(f"Warning: Failed to save assistant message: {e}")
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Flashcards ─────────────────────────────────────────────────────────────────


@app.post("/notebooks/{notebook_id}/flashcards")
async def create_flashcards(notebook_id: str, request: Request):
    data = await request.json()
    deck_id = data.get("deck_id") or str(uuid4())
    topic = data.get("topic", "")
    difficulty = data.get("difficulty", "Medium")
    num_cards = int(data.get("count", 10))
    source_ids = data.get("source_ids", [])

    try:
        embedding_model = get_embedding_model()
        chat_model = get_chat_model()
        result = generate_flashcards(
            chat_model,
            embedding_model,
            notebook_id,
            topic,
            difficulty,
            num_cards,
            source_ids,
        )
        title = result["title"]
        cards = result["flashcards"]

        if cards:
            try:
                db = _db()
                db.save_flashcards(
                    notebook_id,
                    cards,
                    deck_id=deck_id,
                    topic=title,
                    difficulty=difficulty,
                )
            except Exception as save_err:
                print(f"Warning: Failed to save flashcards to DB: {save_err}")

        return {"title": title, "flashcards": cards}
    except Exception as e:
        print(f"Error generating flashcards: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/notebooks/{notebook_id}/flashcards")
async def get_flashcards(notebook_id: str):
    try:
        db = _db()
        rows = db.list_flashcards(notebook_id)

        decks_map = {}
        for row in rows:
            deck_id = row.get("deck_id") or "default"
            if deck_id not in decks_map:
                decks_map[deck_id] = {
                    "id": deck_id,
                    "topic": row.get("topic") or "Saved Flashcards",
                    "difficulty": row.get("difficulty") or "Medium",
                    "createdAt": row.get("created_at"),
                    "cards": [],
                }
            decks_map[deck_id]["cards"].append(
                {"question": row["question"], "answer": row["answer"]}
            )

        return {"decks": list(decks_map.values())}
    except Exception as e:
        print(f"Error fetching flashcards: {e}")
        import traceback

        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.delete("/notebooks/{notebook_id}/flashcards/{deck_id}")
async def delete_flashcard_deck(notebook_id: str, deck_id: str):
    """Delete a flashcard deck."""
    try:
        db = _db()
        db.delete_flashcard_deck(deck_id)
        return {"message": "Flashcard deck deleted successfully"}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── Audio Overview ────────────────────────────────────────────────────────────


@app.post("/notebooks/{notebook_id}/audio")
async def generate_audio_overview(notebook_id: str, request: Request):
    data = await request.json()
    language = data.get("language", "English")
    focus = data.get("focus", "")
    format_type = data.get("format", "Deep Dive")
    length = data.get("length", "Short")
    source_ids = data.get("source_ids", [])

    topic = f"Format: {format_type}."
    if focus:
        topic += f" Special focus/instructions: {focus}."

    try:
        import queue
        import threading

        from audio.audio_gen import generate_podcast_audio
        from audio.script_gen import generate_podcast_script

        def stream_audio():
            yield b"\0" * 1024

            q = queue.Queue()

            def worker():
                try:
                    script_text = generate_podcast_script(
                        chat_model=get_chat_model(),
                        embedding_model=get_embedding_model(),
                        notebook_id=notebook_id,
                        topic=topic,
                        language=language,
                        format=format_type,
                        length=length,
                        source_ids=source_ids,
                    )

                    for chunk in generate_podcast_audio(script_text, language=language):
                        q.put(("audio", chunk))

                    q.put(("done", None))
                except Exception as e:
                    q.put(("error", str(e)))

            t = threading.Thread(target=worker)
            t.start()

            while True:
                try:
                    msg_type, data = q.get(timeout=2.0)
                    if msg_type == "audio":
                        yield data
                    elif msg_type == "done":
                        break
                    elif msg_type == "error":
                        raise Exception(data)
                except queue.Empty:
                    yield b"\0" * 1024

        return StreamingResponse(stream_audio(), media_type="audio/mpeg")
    except Exception as e:
        print(f"Error generating audio overview: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── Podcasts ──────────────────────────────────────────────────────────────────


@app.get("/notebooks/{notebook_id}/podcasts")
async def get_podcasts(notebook_id: str):
    """List all podcasts for a notebook."""
    try:
        db = _db()
        podcasts = db.list_podcasts(notebook_id)
        return podcasts
    except Exception as e:
        print(f"Error listing podcasts: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/notebooks/{notebook_id}/podcasts")
async def add_podcast(
    notebook_id: str,
    audio: UploadFile = File(...),
    format: str = Form("Podcast"),
    language: str = Form("English"),
):
    """Upload a generated podcast audio and save its metadata."""
    db = _db()
    data = await audio.read()

    try:
        gridfs_file_id = db.upload_podcast_audio(notebook_id, data)
        podcast = db.save_podcast(notebook_id, gridfs_file_id, format, language)
        return podcast
    except Exception as e:
        print(f"Error saving podcast: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.delete("/notebooks/{notebook_id}/podcasts/{podcast_id}")
async def delete_podcast(notebook_id: str, podcast_id: str):
    """Delete a podcast."""
    try:
        db = _db()
        db.delete_podcast(podcast_id)
        return {"success": True}
    except Exception as e:
        print(f"Error deleting podcast: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/audio/{file_id}")
async def stream_audio(file_id: str):
    """Stream audio from GridFS by file ID."""
    try:
        db = _db()
        audio_data = db.download_source_file(file_id)
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )
    except Exception as e:
        print(f"Error streaming audio: {e}")
        return JSONResponse(content={"error": "Audio file not found"}, status_code=404)


# ── Mind Maps ─────────────────────────────────────────────────────────────────


@app.get("/notebooks/{notebook_id}/mindmaps")
async def get_mindmaps(notebook_id: str):
    """List all mind maps for a notebook."""
    try:
        db = _db()
        mindmaps = db.list_mindmaps(notebook_id)
        return mindmaps
    except Exception as e:
        print(f"Error listing mind maps: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/notebooks/{notebook_id}/mindmaps")
async def add_mindmap(notebook_id: str, request: Request):
    """Generate and save a new mind map."""
    try:
        data = await request.json()
        topic = data.get("topic", "General Overview")
        language = data.get("language", "English")
        source_ids = data.get("source_ids", [])

        from ingestion.embedder import get_embedding_model
        from mindmap.mindmapgen import generate_mindmap_json

        mindmap_data = generate_mindmap_json(
            embedding_model=get_embedding_model(),
            notebook_id=notebook_id,
            topic=topic,
            language=language,
            source_ids=source_ids,
        )

        db = _db()
        saved = db.save_mindmap(notebook_id, topic, mindmap_data)

        return saved
    except Exception as e:
        print(f"Error generating mind map: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.delete("/notebooks/{notebook_id}/mindmaps/{mindmap_id}")
async def delete_mindmap(notebook_id: str, mindmap_id: str):
    """Delete a mind map."""
    try:
        db = _db()
        db.delete_mindmap(mindmap_id)
        return {"success": True}
    except Exception as e:
        print(f"Error deleting mind map: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
