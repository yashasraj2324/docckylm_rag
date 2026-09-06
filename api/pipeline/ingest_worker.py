"""
Background ingestion worker with retry logic.

Wraps the ingest() function with:
  - Exponential backoff retry (3 attempts)
  - Structured error logging
  - Automatic status transitions (indexing → ready / failed)
  - Temp file cleanup guarantee
"""

import os
import time
import traceback


def _ingest_with_retry(
    embedding_model,
    file_path,
    original_file_name,
    notebook_id,
    source_id,
    *,
    max_retries=3,
    backoff_base=2,
):
    """
    Attempt ingestion with exponential backoff.

    Retries on transient failures (network timeouts, embedding API throttling).
    Raises on the final attempt if still failing.
    """
    from pipeline.ingest import ingest

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            ingest(embedding_model, file_path, original_file_name, notebook_id, source_id)
            return  # success
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                wait = backoff_base ** (attempt - 1)  # 1s, 2s, 4s
                print(
                    f"[ingest] source {source_id} attempt {attempt}/{max_retries} "
                    f"failed: {exc}. Retrying in {wait}s..."
                )
                time.sleep(wait)
            else:
                print(
                    f"[ingest] source {source_id} exhausted {max_retries} retries. "
                    f"Final error: {exc}"
                )

    raise last_error


def _ingest_web_with_retry(
    embedding_model,
    url,
    notebook_id,
    source_id,
    *,
    max_retries=3,
    backoff_base=2,
):
    """Web URL ingestion with retry — same backoff strategy."""
    from web.ingest import ingest_web_url

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            ingest_web_url(embedding_model, url, notebook_id, source_id)
            return
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                wait = backoff_base ** (attempt - 1)
                print(
                    f"[ingest] web source {source_id} attempt {attempt}/{max_retries} "
                    f"failed: {exc}. Retrying in {wait}s..."
                )
                time.sleep(wait)
            else:
                print(
                    f"[ingest] web source {source_id} exhausted {max_retries} retries. "
                    f"Final error: {exc}"
                )

    raise last_error


def process_file_source(db, embedding_model, temp_path, file_name, notebook_id, source_id):
    """
    Full lifecycle for a file-based source ingestion.

    Handles: retry → status update → auto-naming → temp cleanup.
    Designed to be called from a background thread.
    """
    try:
        _ingest_with_retry(embedding_model, temp_path, file_name, notebook_id, source_id)
        db.update_source_status(source_id, "ready")

        # Auto-name if it's the first upload
        _try_auto_name(db, notebook_id)

    except Exception as exc:
        print(f"[ingest] File ingestion permanently failed for source {source_id}: {exc}")
        traceback.print_exc()
        db.update_source_status(source_id, "failed")
    finally:
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


def process_web_source(db, embedding_model, url, notebook_id, source_id):
    """
    Full lifecycle for a web URL source ingestion.

    Handles: retry → status update → auto-naming.
    Designed to be called from a background thread.
    """
    try:
        _ingest_web_with_retry(embedding_model, url, notebook_id, source_id)
        db.update_source_status(source_id, "ready")

        _try_auto_name(db, notebook_id)

    except Exception as exc:
        print(f"[ingest] Web ingestion permanently failed for source {source_id}: {exc}")
        traceback.print_exc()
        db.update_source_status(source_id, "failed")


def process_search_results(db, embedding_model, results, notebook_id):
    """
    Ingest multiple search result URLs with per-item retry.

    Each URL is retried independently — one bad URL won't block the others.
    """
    for item in results:
        source_id = item["source"]["id"]
        url = item["result_data"]["url"]
        try:
            _ingest_web_with_retry(embedding_model, url, notebook_id, source_id)
            db.update_source_status(source_id, "ready")
        except Exception as exc:
            print(f"[ingest] Search result ingestion failed for source {source_id}: {exc}")
            db.update_source_status(source_id, "failed")

    _try_auto_name(db, notebook_id)


def _try_auto_name(db, notebook_id):
    """Auto-name the notebook if it still has the default title."""
    try:
        notebooks = db.list_notebooks()
        nb = next((n for n in notebooks if n["id"] == notebook_id), None)
        if nb and nb["title"] == "Untitled notebook":
            from pipeline.naming import generate_notebook_title

            new_title = generate_notebook_title(notebook_id)
            db.rename_notebook(notebook_id, new_title)
    except Exception as exc:
        print(f"[ingest] Auto-naming failed for notebook {notebook_id}: {exc}")
