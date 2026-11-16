import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from cache.redis_client import (
    get_cached_response,
    set_cached_response,
)
from ingestion.embedder import get_embedding_model
from ingestion.extractor import load_asset
from llm.chat_model import get_chat_model
from pipeline.query import context_supports_query, prepare_answer, stream_answer
from routes.dependencies import get_db


router = APIRouter(tags=["Chat"])


@router.get("/notebooks/{notebook_id}/messages")
async def list_messages(notebook_id: str):
    """Return full message history for a notebook."""
    return get_db().list_messages(notebook_id)


@router.post("/notebooks/{notebook_id}/chat")
async def chat_stream(notebook_id: str, request: Request):
    """SSE streaming RAG chat endpoint."""
    body = await request.json()
    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse(content={"error": "query is required"}, status_code=400)

    db = get_db()

    try:
        db.save_message(notebook_id, "user", query)
    except Exception as e:
        print(f"Warning: Failed to save user message: {e}")

    try:
        history = db.list_messages(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to fetch message history: {e}")
        history = []

    def generate():
        full_answer = []
        citations = []

        def asset_loader(source_id, asset_id):
            source = next(
                source
                for source in db.list_sources(notebook_id)
                if source["id"] == source_id
            )
            return load_asset(
                db.download_source_file(source["gridfs_file_id"]),
                source["file_name"],
                asset_id,
            )

        try:
            cached = get_cached_response(notebook_id, query)
            if cached:
                answer = cached.get("answer", "")
                citations = cached.get("citations", [])
                yield f"data: {json.dumps({'type': 'chunk', 'content': answer})}\n\n"
                if citations:
                    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
                yield "data: [DONE]\n\n"
                return
        except Exception:
            pass

        try:
            embedding_model = get_embedding_model()
            chat_model = get_chat_model()
            prompt, citations, _ctx, has_context = prepare_answer(
                embedding_model,
                query,
                notebook_id,
                history=history,
                asset_loader=asset_loader,
            )

            if not has_context or not context_supports_query(chat_model, query, _ctx):
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
                try:
                    set_cached_response(notebook_id, query, answer_text, citations)
                except Exception:
                    pass
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
