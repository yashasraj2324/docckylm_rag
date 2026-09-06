"""
Database facade for MongoDB + GridFS.

Replaces SupabaseDB. Same method signatures so index.py and ingest_worker.py
don't need changes beyond the import statement.
"""

from typing import Any
from bson import ObjectId

from db.mongo_client import build_client
from db.flashcards import (
    delete_flashcard_deck,
    delete_flashcards,
    list_flashcards,
    save_flashcards,
)
from db.messages import list_messages, save_message
from db.mindmaps import delete_mindmap, list_mindmaps, save_mindmap
from db.notebooks import (
    create_notebook,
    delete_notebook_rows,
    list_notebooks,
    rename_notebook,
)
from db.podcasts import (
    delete_podcast,
    list_podcasts,
    save_podcast,
    upload_podcast_audio,
)
from db.sources import (
    create_source,
    delete_source_row,
    delete_storage_paths,
    delete_storage_prefix,
    list_sources,
    update_source_status,
    upload_source,
)
from db.gridfs_client import download_file


class Database:
    """
    MongoDB + GridFS backend with the same interface as the old SupabaseDB.
    """

    def __init__(self):
        self.db, self.pdf_bucket, self.audio_bucket, self.user_id = build_client()

    # Notebooks

    def list_notebooks(self) -> list[dict[str, Any]]:
        return list_notebooks(self.db, self.user_id)

    def create_notebook(self, title: str = "Untitled notebook") -> dict[str, Any]:
        return create_notebook(self.db, self.user_id, title)

    def rename_notebook(self, notebook_id: str, title: str) -> dict[str, Any]:
        return rename_notebook(self.db, self.user_id, notebook_id, title)

    def delete_notebook_rows(self, notebook_id: str) -> None:
        """
        Cascade delete: delete GridFS files for all sources, then delete
        all child collection rows, then the notebook itself.
        """
        delete_storage_prefix(self.pdf_bucket, self.db, notebook_id)
        for collection in ("sources", "messages", "flashcards", "podcasts", "mindmaps"):
            getattr(self.db, collection).delete_many(
                {"notebook_id": ObjectId(notebook_id)}
            )
        delete_notebook_rows(self.db, self.user_id, notebook_id)

    # Sources

    def create_source(
        self,
        notebook_id: str,
        source_id: str,
        file_name: str,
        storage_path: str,
        status: str = "indexing",
        source_type: str = "pdf",
        content_type: str = "application/pdf",
    ) -> dict[str, Any]:
        return create_source(
            self.db,
            notebook_id,
            source_id,
            file_name,
            storage_path,
            status,
            source_type,
            content_type,
        )

    def update_source_status(self, source_id: str, status: str) -> None:
        update_source_status(self.db, source_id, status)

    def list_sources(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_sources(self.db, notebook_id)

    def delete_source_row(self, source_id: str) -> None:
        delete_source_row(self.db, source_id)

    def upload_source(
        self,
        notebook_id: str,
        source_id: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        return upload_source(
            self.pdf_bucket,
            self.user_id,
            notebook_id,
            source_id,
            file_name,
            data,
            content_type,
        )

    def delete_storage_paths(self, storage_paths: list[str]) -> None:
        delete_storage_paths(self.pdf_bucket, storage_paths)

    def delete_storage_prefix(self, notebook_id: str) -> None:
        delete_storage_prefix(self.pdf_bucket, self.db, notebook_id)

    def download_source_file(self, gridfs_file_id: str) -> bytes:
        """Download a source file from GridFS (used by retry endpoint)."""
        return download_file(self.pdf_bucket, gridfs_file_id)

    def download_podcast_file(self, gridfs_file_id: str) -> bytes:
        """Download generated podcast audio from the podcasts GridFS bucket."""
        try:
            return download_file(self.audio_bucket, gridfs_file_id)
        except Exception:
            # Older podcast records were accidentally written to the source
            # bucket; keep them playable while new files use podcasts_fs.
            return download_file(self.pdf_bucket, gridfs_file_id)

    # Messages

    def save_message(
        self,
        notebook_id: str,
        role: str,
        content: str,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        return save_message(self.db, notebook_id, role, content, sources)

    def list_messages(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_messages(self.db, notebook_id)

    # Flashcards

    def save_flashcards(
        self,
        notebook_id: str,
        flashcards: list[dict[str, str]],
        deck_id: str = None,
        topic: str = None,
        difficulty: str = None,
    ) -> None:
        save_flashcards(
            self.db, notebook_id, flashcards, deck_id, topic, difficulty
        )

    def list_flashcards(self, notebook_id: str) -> list[dict[str, str]]:
        return list_flashcards(self.db, notebook_id)

    def delete_flashcards(self, notebook_id: str) -> None:
        delete_flashcards(self.db, notebook_id)

    def delete_flashcard_deck(self, deck_id: str) -> None:
        delete_flashcard_deck(self.db, deck_id)

    # Podcasts

    def save_podcast(
        self, notebook_id: str, gridfs_file_id: str, format: str, language: str
    ) -> dict[str, Any]:
        return save_podcast(self.db, notebook_id, gridfs_file_id, format, language)

    def list_podcasts(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_podcasts(self.db, notebook_id)

    def delete_podcast(self, podcast_id: str) -> None:
        delete_podcast(self.db, podcast_id)

    def upload_podcast_audio(self, notebook_id: str, data: bytes) -> str:
        return upload_podcast_audio(
            self.audio_bucket, self.user_id, notebook_id, data
        )

    # Mind Maps

    def list_mindmaps(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_mindmaps(self.db, notebook_id)

    def save_mindmap(
        self, notebook_id: str, topic: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return save_mindmap(self.db, notebook_id, topic, data)

    def delete_mindmap(self, mindmap_id: str) -> None:
        delete_mindmap(self.db, mindmap_id)

    # Utilities

    def next_source_id(self) -> str:
        return str(ObjectId())
