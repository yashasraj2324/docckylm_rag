"""
Message CRUD operations for MongoDB.

Replaces Supabase version. sources_json JSONB to native BSON array.
"""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.database import Database as MongoDatabase

from db.mongo_client import _serialize_doc
from db.notebooks import touch_notebook


def save_message(
    db: MongoDatabase,
    notebook_id: str,
    role: str,
    content: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "notebook_id": ObjectId(notebook_id),
        "role": role,
        "content": content,
        "sources_json": sources or [],
        "created_at": now,
    }
    db.messages.insert_one(doc)
    touch_notebook(db, notebook_id)
    return _serialize_doc(doc)


def list_messages(db: MongoDatabase, notebook_id: str) -> list[dict[str, Any]]:
    docs = list(
        db.messages.find({"notebook_id": ObjectId(notebook_id)}).sort("created_at", 1)
    )
    return [
        {
            "role": doc["role"],
            "content": doc["content"],
            "sources": doc.get("sources_json") or [],
        }
        for doc in docs
    ]
