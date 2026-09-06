import threading
from uuid import uuid4

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ingestion.embedder import get_embedding_model
from llm.chat_model import get_chat_model
from pipeline.flashcards import generate_flashcards
from routes.dependencies import get_db


router = APIRouter(tags=["Generated Content"])


@router.post("/notebooks/{notebook_id}/flashcards")
async def create_flashcards(notebook_id: str, request: Request):
    data = await request.json()
    deck_id = data.get("deck_id") or str(uuid4())
    topic = data.get("topic", "")
    difficulty = data.get("difficulty", "Medium")
    num_cards = int(data.get("count", 10))
    source_ids = data.get("source_ids", [])

    try:
        embedding_model = get_embedding_model()
        from llm.chat_model import get_chat_model

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
                get_db().save_flashcards(
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


@router.get("/notebooks/{notebook_id}/flashcards")
async def get_flashcards(notebook_id: str):
    try:
        rows = get_db().list_flashcards(notebook_id)

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


@router.delete("/notebooks/{notebook_id}/flashcards/{deck_id}")
async def delete_flashcard_deck(notebook_id: str, deck_id: str):
    """Delete a flashcard deck."""
    try:
        get_db().delete_flashcard_deck(deck_id)
        return {"message": "Flashcard deck deleted successfully"}
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/notebooks/{notebook_id}/audio")
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

        from audio.audio_gen import generate_podcast_audio
        from audio.script_gen import generate_podcast_script

        def stream_audio():
            q: queue.Queue = queue.Queue()

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
                    msg_type, data = q.get(timeout=30.0)
                    if msg_type == "audio":
                        yield data
                    elif msg_type == "done":
                        break
                    elif msg_type == "error":
                        raise Exception(data)
                except queue.Empty:
                    break

        return StreamingResponse(
            stream_audio(),
            media_type="audio/mpeg",
            headers={"X-Accel-Buffering": "no"},
        )
    except Exception as e:
        print(f"Error generating audio overview: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/notebooks/{notebook_id}/podcasts")
async def get_podcasts(notebook_id: str):
    """List all podcasts for a notebook."""
    try:
        return get_db().list_podcasts(notebook_id)
    except Exception as e:
        print(f"Error listing podcasts: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/notebooks/{notebook_id}/podcasts")
async def add_podcast(
    notebook_id: str,
    audio: UploadFile = File(...),
    format: str = Form("Podcast"),
    language: str = Form("English"),
):
    """Upload a generated podcast audio and save its metadata."""
    db = get_db()
    data = await audio.read()

    try:
        gridfs_file_id = db.upload_podcast_audio(notebook_id, data)
        return db.save_podcast(notebook_id, gridfs_file_id, format, language)
    except Exception as e:
        print(f"Error saving podcast: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.delete("/notebooks/{notebook_id}/podcasts/{podcast_id}")
async def delete_podcast(notebook_id: str, podcast_id: str):
    """Delete a podcast."""
    try:
        get_db().delete_podcast(podcast_id)
        return {"success": True}
    except Exception as e:
        print(f"Error deleting podcast: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/audio/{file_id}")
async def stream_audio(file_id: str):
    """Stream audio from GridFS by file ID."""
    try:
        audio_data = get_db().download_podcast_file(file_id)
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


@router.get("/notebooks/{notebook_id}/mindmaps")
async def get_mindmaps(notebook_id: str):
    """List all mind maps for a notebook."""
    try:
        return get_db().list_mindmaps(notebook_id)
    except Exception as e:
        print(f"Error listing mind maps: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/notebooks/{notebook_id}/mindmaps")
async def add_mindmap(notebook_id: str, request: Request):
    """Generate and save a new mind map."""
    try:
        data = await request.json()
        topic = data.get("topic", "General Overview")
        language = data.get("language", "English")
        source_ids = data.get("source_ids", [])

        from mindmap.mindmapgen import generate_mindmap_json

        mindmap_data = generate_mindmap_json(
            embedding_model=get_embedding_model(),
            notebook_id=notebook_id,
            topic=topic,
            language=language,
            source_ids=source_ids,
        )

        return get_db().save_mindmap(notebook_id, topic, mindmap_data)
    except Exception as e:
        print(f"Error generating mind map: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.delete("/notebooks/{notebook_id}/mindmaps/{mindmap_id}")
async def delete_mindmap(notebook_id: str, mindmap_id: str):
    """Delete a mind map."""
    try:
        get_db().delete_mindmap(mindmap_id)
        return {"success": True}
    except Exception as e:
        print(f"Error deleting mind map: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
