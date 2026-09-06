"""
Source CRUD operations for MongoDB.

Replaces Supabase version. File storage uses GridFS instead of Supabase Storage.
The `storage_path` field becomes `gridfs_file_id` (ObjectId stored as string).
"""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from gridfs import GridFSBucket
from pymongo.database import Database as MongoDatabase

from db.gridfs_client import (
    delete_file,
    delete_files_by_notebook,
    upload_file,
)
from db.mongo_client import _serialize_doc, safe_file_name
from db.notebooks import touch_notebook


def create_source(
    db: MongoDatabase,
    notebook_id: str,
    source_id: str,
    file_name: str,
    gridfs_file_id: str,
    status: str = "indexing",
    source_type: str = "pdf",
    content_type: str = "application/pdf",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(source_id),
        "notebook_id": ObjectId(notebook_id),
        "source_type": source_type,
        "file_name": file_name,
        "content_type": content_type,
        "gridfs_file_id": ObjectId(gridfs_file_id) if gridfs_file_id and gridfs_file_id != "web" else gridfs_file_id,
        "status": status,
        "created_at": now,
    }
    db.sources.insert_one(doc)
    touch_notebook(db, notebook_id)
    return _serialize_doc(doc)


def update_source_status(db: MongoDatabase, source_id: str, status: str) -> None:
    db.sources.update_one(
        {"_id": ObjectId(source_id)}, {"$set": {"status": status}}
    )


def list_sources(db: MongoDatabase, notebook_id: str) -> list[dict[str, Any]]:
    docs = list(
        db.sources.find({"notebook_id": ObjectId(notebook_id)}).sort("created_at", 1)
    )
    return [_serialize_doc(d) for d in docs]


def delete_source_row(db: MongoDatabase, source_id: str) -> None:
    db.sources.delete_one({"_id": ObjectId(source_id)})


def upload_pdf(
    bucket: GridFSBucket,
    user_id: str,
    notebook_id: str,
    source_id: str,
    file_name: str,
    data: bytes,
    content_type: str = "application/pdf",
) -> str:
    """Upload a source file to GridFS, return the file ID as string."""
    file_id = upload_file(
        bucket,
        data,
        filename=safe_file_name(file_name),
        metadata={
            "user_id": user_id,
            "notebook_id": notebook_id,
            "source_id": source_id,
            "content_type": content_type,
        },
    )
    return str(file_id)


def delete_storage_paths(bucket: GridFSBucket, storage_paths: list[str]) -> None:
    """Delete GridFS files by their IDs (stored as strings)."""
    for path in storage_paths:
        if path and path not in ("web", "search"):
            try:
                delete_file(bucket, path)
            except Exception:
                pass


def delete_storage_prefix(
    bucket: GridFSBucket, db: MongoDatabase, notebook_id: str
) -> None:
    """Delete all GridFS files for sources belonging to a notebook."""
    delete_files_by_notebook(bucket, db, notebook_id)
