from typing import Any
from uuid import uuid4

from db.client import build_client
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
    upload_pdf,
)


class SupabaseDB:
    def __init__(self):
        self.client, self.url, self.bucket, self.user_id = build_client()

    # ── Notebooks ─────────────────────────────────────────────────────────────

    def list_notebooks(self) -> list[dict[str, Any]]:
        return list_notebooks(self.client, self.user_id)

    def create_notebook(self, title: str = "Untitled notebook") -> dict[str, Any]:
        return create_notebook(self.client, self.user_id, title)

    def rename_notebook(self, notebook_id: str, title: str) -> dict[str, Any]:
        return rename_notebook(self.client, self.user_id, notebook_id, title)

    def delete_notebook_rows(self, notebook_id: str) -> None:
        delete_notebook_rows(self.client, self.user_id, notebook_id)

    # ── Sources ───────────────────────────────────────────────────────────────

    def create_source(
        self,
        notebook_id: str,
        source_id: str,
        file_name: str,
        storage_path: str,
        status: str = "indexing",
    ) -> dict[str, Any]:
        return create_source(
            self.client, notebook_id, source_id, file_name, storage_path, status
        )

    def update_source_status(self, source_id: str, status: str) -> None:
        update_source_status(self.client, source_id, status)

    def list_sources(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_sources(self.client, notebook_id)

    def delete_source_row(self, source_id: str) -> None:
        delete_source_row(self.client, source_id)

    def upload_pdf(
        self,
        notebook_id: str,
        source_id: str,
        file_name: str,
        data: bytes,
    ) -> str:
        return upload_pdf(
            self.client,
            self.bucket,
            self.user_id,
            notebook_id,
            source_id,
            file_name,
            data,
        )

    def delete_storage_paths(self, storage_paths: list[str]) -> None:
        delete_storage_paths(self.client, self.bucket, storage_paths)

    def delete_storage_prefix(self, notebook_id: str) -> None:
        delete_storage_prefix(self.client, self.bucket, self.user_id, notebook_id)

    # ── Messages ──────────────────────────────────────────────────────────────

    def save_message(
        self,
        notebook_id: str,
        role: str,
        content: str,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        return save_message(self.client, notebook_id, role, content, sources)

    def list_messages(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_messages(self.client, notebook_id)

    # ── Flashcards ────────────────────────────────────────────────────────────

    def save_flashcards(
        self,
        notebook_id: str,
        flashcards: list[dict[str, str]],
        deck_id: str = None,
        topic: str = None,
        difficulty: str = None,
    ) -> None:
        save_flashcards(
            self.client, notebook_id, flashcards, deck_id, topic, difficulty
        )

    def list_flashcards(self, notebook_id: str) -> list[dict[str, str]]:
        return list_flashcards(self.client, notebook_id)

    def delete_flashcards(self, notebook_id: str) -> None:
        delete_flashcards(self.client, notebook_id)

    def delete_flashcard_deck(self, deck_id: str) -> None:
        delete_flashcard_deck(self.client, deck_id)

    # ── Podcasts ──────────────────────────────────────────────────────────────

    def save_podcast(
        self, notebook_id: str, audio_url: str, format: str, language: str
    ) -> dict[str, Any]:
        return save_podcast(self.client, notebook_id, audio_url, format, language)

    def list_podcasts(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_podcasts(self.client, notebook_id)

    def delete_podcast(self, podcast_id: str) -> None:
        delete_podcast(self.client, podcast_id)

    def upload_podcast_audio(self, notebook_id: str, data: bytes) -> str:
        return upload_podcast_audio(self.client, self.user_id, notebook_id, data)

    # ── Mind Maps ─────────────────────────────────────────────────────────────

    def list_mindmaps(self, notebook_id: str) -> list[dict[str, Any]]:
        return list_mindmaps(self.client, notebook_id)

    def save_mindmap(
        self, notebook_id: str, topic: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return save_mindmap(self.client, notebook_id, topic, data)

    def delete_mindmap(self, mindmap_id: str) -> None:
        delete_mindmap(self.client, mindmap_id)

    # ── Utilities ─────────────────────────────────────────────────────────────

    def next_source_id(self) -> str:
        return str(uuid4())
