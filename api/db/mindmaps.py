"""
Mind map CRUD operations for MongoDB.

Replaces Supabase version. JSONB to native BSON sub-document (no change needed).
"""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.database import Database as MongoDatabase

from db.mongo_client import _serialize_doc
from db.notebooks import touch_notebook


def list_mindmaps(db: MongoDatabase, notebook_id: str) -> list[dict[str, Any]]:
    docs = list(
        db.mindmaps.find({"notebook_id": ObjectId(notebook_id)}).sort("created_at", -1)
    )
    return [_serialize_doc(d) for d in docs]


def save_mindmap(
    db: MongoDatabase, notebook_id: str, topic: str, data: dict[str, Any]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "notebook_id": ObjectId(notebook_id),
        "topic": topic,
        "data": data,
        "created_at": now,
    }
    db.mindmaps.insert_one(doc)
    touch_notebook(db, notebook_id)
    return _serialize_doc(doc)


def delete_mindmap(db: MongoDatabase, mindmap_id: str) -> None:
    db.mindmaps.delete_one({"_id": ObjectId(mindmap_id)})
