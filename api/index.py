import json
import os
import sys
import tempfile
import threading
from uuid import uuid4

from flask import Flask, Response, jsonify, request, stream_with_context

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bson import ObjectId
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
from cache.redis_client import (
    get_cached_response,
    set_cached_response,
    invalidate_notebook_cache,
)

Database().list_notebooks()
print("Connected to MongoDB successfully")

app = Flask(__name__)

thread_local = threading.local()


def _db():
    if not hasattr(thread_local, "db_instance"):
        thread_local.db_instance = Database()
    return thread_local.db_instance


# ── Health ────────────────────────────────────────────────────────────────────


@app.route("/")
def python_route():
    return jsonify(message="Hello from Flask!")


# ── Notebooks ─────────────────────────────────────────────────────────────────


@app.route("/notebooks", methods=["GET"])
def list_notebooks():
    """Return all notebooks for the demo user, ordered by most-recently updated."""
    db = _db()
    notebooks = db.list_notebooks()
    return jsonify(notebooks)


@app.route("/notebooks", methods=["POST"])
def create_notebook():
    """Create a new notebook.  Body (JSON): { "title": "..." }  (optional)."""
    db = _db()
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "Untitled notebook").strip()
    notebook = db.create_notebook(title=title)
    return jsonify(notebook), 201


@app.route("/notebooks/<notebook_id>", methods=["DELETE"])
def delete_notebook(notebook_id):
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

    # 3. Delete from MongoDB
    db.delete_notebook_rows(notebook_id)

    return jsonify({"success": True})


@app.route("/notebooks/<notebook_id>/auto-name", methods=["POST"])
def auto_name_notebook(notebook_id):
    """Generate a dynamic title for the notebook based on its uploaded content."""
    try:
        title = generate_notebook_title(notebook_id)
        db = _db()
        db.rename_notebook(notebook_id, title)
        return jsonify({"title": title}), 200
    except Exception as e:
        print(f"Error auto-naming notebook {notebook_id}: {e}")
        return jsonify({"error": str(e)}), 500


# ── Sources ───────────────────────────────────────────────────────────────────


@app.route("/notebooks/<notebook_id>/sources", methods=["GET"])
def list_sources(notebook_id):
    """Return all sources for a notebook."""
    db = _db()
    sources = db.list_sources(notebook_id)
    return jsonify(sources)


@app.route("/notebooks/<notebook_id>/sources", methods=["POST"])
def add_source(notebook_id):
    """Upload a PDF source."""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    db = _db()
    source_id = db.next_source_id()
    data = file.read()

    # 1. Upload to GridFS
    gridfs_file_id = db.upload_pdf(notebook_id, source_id, file.filename, data)

    # 2. Create DB row
    source = db.create_source(
        notebook_id, source_id, file.filename, gridfs_file_id, "indexing"
    )

    # 3. Save to temp file and run ingest (with retry) in the background
    _, ext = os.path.splitext(file.filename)
    fd, temp_path = tempfile.mkstemp(suffix=ext.lower())
    os.write(fd, data)
    os.close(fd)

    def process():
        embedding_model = get_embedding_model()
        process_file_source(
            db, embedding_model, temp_path, file.filename, notebook_id, source_id
        )

    threading.Thread(target=process).start()

    # Invalidate cached RAG responses for this notebook (new source = new context)
    try:
        invalidate_notebook_cache(notebook_id)
    except Exception:
        pass

    return jsonify(source), 201


@app.route("/notebooks/<notebook_id>/sources/website", methods=["POST"])
def add_website_source(notebook_id):
    req_data = request.get_json()
    if not req_data or "url" not in req_data:
        return jsonify({"error": "Missing url"}), 400

    url = req_data["url"]
    db = _db()
    source_id = db.next_source_id()

    # Store source in DB (we don't upload a file to storage for websites)
    # Using 'web' as a placeholder storage_path since it cannot be null
    source = db.create_source(notebook_id, source_id, url, "web", "indexing")

    def process():
        embedding_model = get_embedding_model()
        process_web_source(db, embedding_model, url, notebook_id, source_id)

    threading.Thread(target=process).start()
    return jsonify(source), 201


@app.route("/notebooks/<notebook_id>/sources/search", methods=["POST"])
def add_search_source(notebook_id):
    req_data = request.get_json()
    if not req_data or "query" not in req_data:
        return jsonify({"error": "Missing query"}), 400

    query = req_data["query"]
    db = _db()

    try:
        results = fetch_search_results(query)
    except Exception as e:
        print(f"Failed to fetch search results: {e}")
        return jsonify({"error": "Search failed"}), 500

    if not results:
        return jsonify({"error": "No results found"}), 404

    created_sources = []
    # Create DB rows for each result
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

    # Return the created sources without the raw result_data payload
    return jsonify([item["source"] for item in created_sources]), 201


@app.route("/notebooks/<notebook_id>/sources/<source_id>", methods=["DELETE"])
def delete_source(notebook_id, source_id):
    """Hard delete a single source from Qdrant, GridFS, and MongoDB."""
    db = _db()

    # Need to know the storage path to delete it from Storage
    # Let's fetch the source first
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

    # Invalidate cached RAG responses for this notebook
    try:
        invalidate_notebook_cache(notebook_id)
    except Exception:
        pass

    return jsonify({"success": True}), 200


@app.route("/notebooks/<notebook_id>/sources/<source_id>/retry", methods=["POST"])
def retry_source(notebook_id, source_id):
    """Retry ingestion for a failed or stuck source."""
    db = _db()
    sources = db.list_sources(notebook_id)
    target_source = next((s for s in sources if s["id"] == source_id), None)

    if not target_source:
        return jsonify({"error": "Source not found"}), 404

    if target_source.get("status") not in ("failed", "indexing"):
        return jsonify({"error": "Source is not in a retryable state"}), 400

    # Clean up any partial vectors from the previous attempt
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
            # File-based source: re-download from GridFS and re-ingest
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
            # Web/search source: re-ingest from URL
            url = file_name  # For web sources, file_name stores the URL
            process_web_source(db, embedding_model, url, notebook_id, source_id)

    threading.Thread(target=process).start()

    return jsonify({"success": True, "status": "indexing"}), 200


# ── Chat ──────────────────────────────────────────────────────────────────────


@app.route("/notebooks/<notebook_id>/messages", methods=["GET"])
def list_messages(notebook_id):
    """Return full message history for a notebook."""
    db = _db()
    messages = db.list_messages(notebook_id)
    return jsonify(messages)


@app.route("/notebooks/<notebook_id>/chat", methods=["POST"])
def chat_stream(notebook_id):
    """SSE streaming RAG chat endpoint."""
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    db = _db()

    # Save user message immediately
    try:
        db.save_message(notebook_id, "user", query)
    except Exception as e:
        print(f"Warning: Failed to save user message: {e}")

    # Fetch conversation history for multi-turn context
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
                # No docs found — stream a graceful message
                no_ctx = "I couldn't find relevant information in your sources. Please add PDFs and try again."
                yield f"data: {json.dumps({'type': 'chunk', 'content': no_ctx})}\n\n"
                full_answer.append(no_ctx)
            else:
                # Stream each token
                for chunk in stream_answer(chat_model, prompt):
                    full_answer.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            # Send citations once streaming is done
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

        except Exception as e:
            err_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': err_msg})}\n\n"
            full_answer.append(err_msg)

        finally:
            # Persist assistant message
            answer_text = "".join(full_answer)
            if answer_text:
                try:
                    db.save_message(notebook_id, "assistant", answer_text, citations)
                except Exception as e:
                    print(f"Warning: Failed to save assistant message: {e}")
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/notebooks/<notebook_id>/flashcards", methods=["POST"])
def create_flashcards(notebook_id):
    data = request.json or {}
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

        return jsonify({"title": title, "flashcards": cards}), 200
    except Exception as e:
        print(f"Error generating flashcards: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/flashcards", methods=["GET"])
def get_flashcards(notebook_id):
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

        return jsonify({"decks": list(decks_map.values())}), 200
    except Exception as e:
        print(f"Error fetching flashcards: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/flashcards/<deck_id>", methods=["DELETE"])
def delete_flashcard_deck(notebook_id, deck_id):
    """Delete a flashcard deck."""
    try:
        db = _db()
        db.delete_flashcard_deck(deck_id)
        return jsonify({"message": "Flashcard deck deleted successfully"})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/audio", methods=["POST"])
def generate_audio_overview(notebook_id):
    data = request.json
    language = data.get("language", "English")
    focus = data.get("focus", "")
    format_type = data.get("format", "Deep Dive")
    length = data.get("length", "Short")
    source_ids = data.get("source_ids", [])

    # Construct a comprehensive topic instruction
    topic = f"Format: {format_type}."
    if focus:
        topic += f" Special focus/instructions: {focus}."

    try:
        import queue
        import threading

        from audio.audio_gen import generate_podcast_audio
        from audio.script_gen import generate_podcast_script

        def stream_audio():
            # Yield padding to flush HTTP headers immediately and prevent proxy timeouts
            yield b"\0" * 1024

            q = queue.Queue()

            def worker():
                try:
                    # 1. Generate the script text
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

                    # 2. Convert script to audio
                    for chunk in generate_podcast_audio(script_text, language=language):
                        q.put(("audio", chunk))

                    q.put(("done", None))
                except Exception as e:
                    q.put(("error", str(e)))

            # Start background generation thread
            t = threading.Thread(target=worker)
            t.start()

            # Continuously poll the queue, yielding padding bytes if empty to keep connection alive
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
                    # Connection keep-alive
                    yield b"\0" * 1024

        return Response(stream_with_context(stream_audio()), mimetype="audio/mpeg")
    except Exception as e:
        print(f"Error generating audio overview: {e}")
        return jsonify({"error": str(e)}), 500


# ── Podcasts ──────────────────────────────────────────────────────────────────


@app.route("/notebooks/<notebook_id>/podcasts", methods=["GET"])
def get_podcasts(notebook_id):
    """List all podcasts for a notebook."""
    try:
        db = _db()
        podcasts = db.list_podcasts(notebook_id)
        return jsonify(podcasts)
    except Exception as e:
        print(f"Error listing podcasts: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/podcasts", methods=["POST"])
def add_podcast(notebook_id):
    """Upload a generated podcast audio and save its metadata."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file part"}), 400

    file = request.files["audio"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    format = request.form.get("format", "Podcast")
    language = request.form.get("language", "English")

    db = _db()
    data = file.read()

    try:
        # 1. Upload audio to GridFS
        gridfs_file_id = db.upload_podcast_audio(notebook_id, data)

        # 2. Save metadata to Database
        podcast = db.save_podcast(notebook_id, gridfs_file_id, format, language)
        return jsonify(podcast)
    except Exception as e:
        print(f"Error saving podcast: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/podcasts/<podcast_id>", methods=["DELETE"])
def delete_podcast(notebook_id, podcast_id):
    """Delete a podcast."""
    try:
        db = _db()
        db.delete_podcast(podcast_id)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting podcast: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/audio/<file_id>", methods=["GET"])
def stream_audio(file_id):
    """Stream audio from GridFS by file ID."""
    try:
        db = _db()
        audio_data = db.download_source_file(file_id)
        return Response(
            audio_data,
            mimetype="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )
    except Exception as e:
        print(f"Error streaming audio: {e}")
        return jsonify({"error": "Audio file not found"}), 404


# ── Mind Maps ─────────────────────────────────────────────────────────────────


@app.route("/notebooks/<notebook_id>/mindmaps", methods=["GET"])
def get_mindmaps(notebook_id):
    """List all mind maps for a notebook."""
    try:
        db = _db()
        mindmaps = db.list_mindmaps(notebook_id)
        return jsonify(mindmaps)
    except Exception as e:
        print(f"Error listing mind maps: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/mindmaps", methods=["POST"])
def add_mindmap(notebook_id):
    """Generate and save a new mind map."""
    try:
        data = request.json
        topic = data.get("topic", "General Overview")
        language = data.get("language", "English")
        source_ids = data.get("source_ids", [])

        from ingestion.embedder import get_embedding_model
        from mindmap.mindmapgen import generate_mindmap_json

        # 1. Generate mind map JSON using LLM
        mindmap_data = generate_mindmap_json(
            embedding_model=get_embedding_model(),
            notebook_id=notebook_id,
            topic=topic,
            language=language,
            source_ids=source_ids,
        )

        # 2. Save to database
        db = _db()
        saved = db.save_mindmap(notebook_id, topic, mindmap_data)

        return jsonify(saved)
    except Exception as e:
        print(f"Error generating mind map: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/notebooks/<notebook_id>/mindmaps/<mindmap_id>", methods=["DELETE"])
def delete_mindmap(notebook_id, mindmap_id):
    """Delete a mind map."""
    try:
        db = _db()
        db.delete_mindmap(mindmap_id)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting mind map: {e}")
        return jsonify({"error": str(e)}), 500
