"""
Notebook CRUD operations for MongoDB.

Replaces the Supabase/PostgREST version. Uses PyMongo's Database object.
All functions return plain dicts with string IDs for JSON serialization.
"""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.database import Database as MongoDatabase

from db.mongo_client import _serialize_doc


def list_notebooks(db: MongoDatabase, user_id: str) -> list[dict[str, Any]]:
    docs = list(
        db.notebooks.find({"user_id": user_id}).sort("updated_at", -1)
    )
    return [_serialize_doc(d) for d in docs]


def create_notebook(
    db: MongoDatabase, user_id: str, title: str = "Untitled notebook"
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "title": title.strip() or "Untitled notebook",
        "created_at": now,
        "updated_at": now,
    }
    result = db.notebooks.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_doc(doc)


def rename_notebook(
    db: MongoDatabase, user_id: str, notebook_id: str, title: str
) -> dict[str, Any]:
    db.notebooks.update_one(
        {"_id": ObjectId(notebook_id), "user_id": user_id},
        {"$set": {"title": title.strip() or "Untitled notebook", "updated_at": datetime.now(timezone.utc)}},
    )
    return {"id": notebook_id, "title": title.strip()}


def delete_notebook_rows(db: MongoDatabase, user_id: str, notebook_id: str) -> None:
    """Delete the notebook row only (child collections handled by base.py cascade)."""
    db.notebooks.delete_one({"_id": ObjectId(notebook_id), "user_id": user_id})


def touch_notebook(db: MongoDatabase, notebook_id: str) -> None:
    """Update notebook's updated_at timestamp (replaces Postgres trigger)."""
    db.notebooks.update_one(
        {"_id": ObjectId(notebook_id)},
        {"$set": {"updated_at": datetime.now(timezone.utc)}},
    )
