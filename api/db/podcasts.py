"""
Podcast CRUD operations for MongoDB + GridFS.

Replaces Supabase version. Audio stored in GridFS bucket 'podcasts_fs'
instead of Supabase Storage public bucket. Served via /audio/<file_id> route.
"""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from gridfs import GridFSBucket
from pymongo.database import Database as MongoDatabase

from db.gridfs_client import upload_file
from db.mongo_client import _serialize_doc
from db.notebooks import touch_notebook


def list_podcasts(db: MongoDatabase, notebook_id: str) -> list[dict[str, Any]]:
    docs = list(
        db.podcasts.find({"notebook_id": ObjectId(notebook_id)}).sort("created_at", -1)
    )
    return [_serialize_doc(d) for d in docs]


def save_podcast(
    db: MongoDatabase,
    notebook_id: str,
    gridfs_file_id: str,
    format: str,
    language: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "notebook_id": ObjectId(notebook_id),
        "gridfs_file_id": ObjectId(gridfs_file_id),
        "format": format,
        "language": language,
        "created_at": now,
    }
    db.podcasts.insert_one(doc)
    touch_notebook(db, notebook_id)
    return _serialize_doc(doc)


def delete_podcast(db: MongoDatabase, podcast_id: str) -> None:
    """Delete podcast metadata. GridFS file cleanup handled by caller."""
    db.podcasts.delete_one({"_id": ObjectId(podcast_id)})


def upload_podcast_audio(
    bucket: GridFSBucket, user_id: str, notebook_id: str, data: bytes
) -> str:
    """Upload podcast audio to GridFS, return the file ID as string."""
    file_id = upload_file(
        bucket,
        data,
        filename=f"{notebook_id}.mp3",
        metadata={
            "user_id": user_id,
            "notebook_id": notebook_id,
            "content_type": "audio/mpeg",
        },
    )
    return str(file_id)
