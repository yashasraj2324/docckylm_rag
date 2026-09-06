

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

# Ensure this package is importable when running from api/
_script_dir = Path(__file__).parent.resolve()
_api_dir = _script_dir.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

from bson import ObjectId

from db import Database
from ingestion.embedder import get_embedding_model
from pipeline.ingest_worker import process_file_source

EVAL_DIR = Path(__file__).parent.resolve()
NOTEBOOK_JSON = EVAL_DIR / ".test_notebook.json"
NOTEBOOK_TITLE = "Eval Test Notebook"
EVAL_PDFS = sorted(EVAL_DIR.glob("*.pdf"))


def load_json(path: Path) -> dict | None:
    """Return parsed JSON or None if the file doesn't exist."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_existing_notebook(db: Database) -> dict | None:
    """Return the existing eval notebook if one is found."""
    notebooks = db.list_notebooks()
    for nb in notebooks:
        if nb.get("title") == NOTEBOOK_TITLE:
            return nb
    return None


def wait_for_sources(db: Database, notebook_id: str, source_ids: list[str], timeout: float = 300) -> bool:
    """
    Poll until all sources reach status="ready" (or timeout after *timeout* seconds).

    Returns True if all sources became ready, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sources = db.list_sources(notebook_id)
        id_map = {s["id"]: s for s in sources}
        ready = all(id_map.get(sid, {}).get("status") == "ready" for sid in source_ids)
        if ready:
            return True
        time.sleep(2)

    return False


def run() -> dict:
    db = Database()
    existing = load_json(NOTEBOOK_JSON)

    # ── 1. Find or create the notebook ────────────────────────────────────────
    notebook = find_existing_notebook(db)

    if notebook:
        print(f"[bootstrap] Found existing notebook: {notebook['id']}")
    else:
        print(f"[bootstrap] Creating notebook '{NOTEBOOK_TITLE}'...")
        notebook = db.create_notebook(title=NOTEBOOK_TITLE)
        print(f"[bootstrap] Created notebook: {notebook['id']}")

    notebook_id = notebook["id"]

    # ── 2. Find PDFs that need to be uploaded ─────────────────────────────────
    pdf_files: list[Path] = []
    for pdf in EVAL_PDFS:
        if pdf.suffix.lower() in (".pdf",):
            pdf_files.append(pdf)

    if not pdf_files:
        print("[bootstrap] No PDF files found in evals/. Nothing to upload.")
        result = {"notebook_id": notebook_id, "sources": []}
        save_json(NOTEBOOK_JSON, result)
        return result

    print(f"[bootstrap] Found {len(pdf_files)} PDF(s): {[p.name for p in pdf_files]}")

    # ── 3. Check which sources already exist in the notebook ─────────────────
    existing_sources = db.list_sources(notebook_id)
    existing_by_name = {Path(s.get("file_name", "")).name: s for s in existing_sources}

    new_sources: list[dict] = []

    for pdf_path in pdf_files:
        name = pdf_path.name
        if name in existing_by_name:
            src = existing_by_name[name]
            print(f"[bootstrap] Source '{name}' already exists (status={src.get('status')}).")
            new_sources.append(src)
        else:
            print(f"[bootstrap] Uploading '{name}'...")
            source_id = db.next_source_id()

            with open(pdf_path, "rb") as fh:
                data = fh.read()

            gridfs_file_id = db.upload_source(
                notebook_id=notebook_id,
                source_id=source_id,
                file_name=name,
                data=data,
                content_type="application/pdf",
            )
            source = db.create_source(
                notebook_id=notebook_id,
                source_id=source_id,
                file_name=name,
                storage_path=gridfs_file_id,
                status="indexing",
                source_type="pdf",
                content_type="application/pdf",
            )
            new_sources.append(source)

            # Kick off background ingestion
            import tempfile

            _, ext = os.path.splitext(name)
            fd, temp_path = tempfile.mkstemp(suffix=ext)
            os.write(fd, data)
            os.close(fd)

            def process(temp_path=temp_path, source_id=source_id):
                embedding_model = get_embedding_model()
                process_file_source(db, embedding_model, temp_path, name, notebook_id, source_id)

            threading.Thread(target=process, daemon=True).start()
            print(f"[bootstrap] Ingestion thread started for '{name}' (source_id={source_id}).")

    # ── 4. Wait for all sources to become ready ──────────────────────────────
    source_ids = [s["id"] for s in new_sources]
    pending = [s for s in new_sources if s.get("status") != "ready"]

    if pending:
        print(f"[bootstrap] Waiting for {len(pending)} source(s) to finish indexing (max 5 min)...")
        success = wait_for_sources(db, notebook_id, source_ids, timeout=300)
        if success:
            print("[bootstrap] All sources are ready.")
        else:
            print("[bootstrap] WARNING: Timed out waiting for some sources to become ready.")
            print("            You can re-run this script later or check the FastAPI logs.")
    else:
        print("[bootstrap] All sources were already ready.")

    # ── 5. Persist IDs ───────────────────────────────────────────────────────
    result = {
        "notebook_id": notebook_id,
        "sources": [{"id": s["id"], "file_name": s.get("file_name"), "status": s.get("status")} for s in new_sources],
    }
    save_json(NOTEBOOK_JSON, result)
    print(f"[bootstrap] Saved notebook IDs to {NOTEBOOK_JSON.relative_to(EVAL_DIR)}")

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("  AI Notebooks — Eval Test Notebook Bootstrap")
    print("=" * 60)
    try:
        result = run()
        print()
        print(f"  notebook_id : {result['notebook_id']}")
        for s in result["sources"]:
            print(f"  source      : {s['id']}  ({s['file_name']})  [{s['status']}]")
        print("=" * 60)
    except Exception as exc:
        print(f"[bootstrap] FATAL: {exc}", file=sys.stderr)
        raise
