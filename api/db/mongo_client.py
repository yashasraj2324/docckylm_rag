"""
MongoDB connection builder and index setup.

Replaces db/client.py (Supabase). Returns a (db, pdf_bucket, audio_bucket, user_id)
tuple consumed by the Database facade in db/base.py.
"""

import os
import re
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient
from gridfs import GridFSBucket

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def safe_file_name(file_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", Path(file_name).name)


def _serialize_doc(doc: dict) -> dict:
    """
    Convert ObjectId fields to strings for JSON serialization.
    Converts _id to id, and stringifies notebook_id / gridfs_file_id if present.
    """
    if doc is None:
        return doc
    result = dict(doc)
    if "_id" in result:
        result["id"] = str(result["_id"])
        del result["_id"]
    for field in ("notebook_id", "gridfs_file_id"):
        val = result.get(field)
        if isinstance(val, ObjectId):
            result[field] = str(val)
    # Also handle datetime to ISO string for JSON
    for field in ("created_at", "updated_at"):
        val = result.get(field)
        if hasattr(val, "isoformat"):
            result[field] = val.isoformat()
    return result


def build_client():
    """
    Read env vars, validate, connect to MongoDB, ensure indexes,
    and return (db, pdf_bucket, audio_bucket, user_id).
    """
    uri = os.getenv("MONGODB_URI", "").strip()
    db_name = os.getenv("MONGODB_DB", "docckylm").strip()
    user_id = os.getenv("DEMO_USER_ID", "").strip()

    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Add your MongoDB connection string to .env.\n"
            "Example: mongodb+srv://user:pass@cluster.mongodb.net/docckylm"
        )
    if not user_id:
        raise RuntimeError(
            "DEMO_USER_ID must be set in .env. Use a fixed UUID "
            "for this single-user demo."
        )

    try:
        UUID(user_id)
    except ValueError as exc:
        raise RuntimeError(
            "DEMO_USER_ID must be a valid UUID. Generate one with: "
            'python -c "import uuid; print(uuid.uuid4())"'
        ) from exc

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]

    # Ensure indexes (idempotent - safe to call on every startup)
    db.notebooks.create_index(
        [("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_updated"
    )
    db.sources.create_index(
        [("notebook_id", ASCENDING), ("created_at", ASCENDING)], name="nb_created"
    )
    db.messages.create_index(
        [("notebook_id", ASCENDING), ("created_at", ASCENDING)], name="nb_created"
    )
    db.flashcards.create_index(
        [("notebook_id", ASCENDING), ("deck_id", ASCENDING), ("card_order", ASCENDING)],
        name="nb_deck_order",
    )
    db.podcasts.create_index(
        [("notebook_id", ASCENDING), ("created_at", DESCENDING)], name="nb_created"
    )
    db.mindmaps.create_index(
        [("notebook_id", ASCENDING), ("created_at", DESCENDING)], name="nb_created"
    )

    # GridFS buckets for file storage
    pdf_bucket = GridFSBucket(db, bucket_name="fs")
    audio_bucket = GridFSBucket(db, bucket_name="podcasts_fs")

    return db, pdf_bucket, audio_bucket, user_id
