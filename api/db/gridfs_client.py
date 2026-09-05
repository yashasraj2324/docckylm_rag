"""
GridFS helpers for uploading, downloading, and deleting files.

Replaces Supabase Storage operations. Two buckets:
  - fs          uploaded PDFs (private, accessed by source_id)
  - podcasts_fs generated podcast MP3s (streamed via /audio/<id> route)
"""

from bson import ObjectId
from gridfs import GridFSBucket


def upload_file(bucket: GridFSBucket, data: bytes, filename: str, metadata: dict) -> ObjectId:
    """Upload bytes to GridFS, return the file ID."""
    grid_in = bucket.open_upload_stream(filename=filename, metadata=metadata)
    grid_in.write(data)
    grid_in.close()
    return grid_in._id


def download_file(bucket: GridFSBucket, file_id) -> bytes:
    """Download file bytes from GridFS by ID (accepts ObjectId or string)."""
    oid = ObjectId(file_id) if not isinstance(file_id, ObjectId) else file_id
    grid_out = bucket.open_download_stream(oid)
    return grid_out.read()


def delete_file(bucket: GridFSBucket, file_id) -> None:
    """Delete a file from GridFS (removes all chunks)."""
    oid = ObjectId(file_id) if not isinstance(file_id, ObjectId) else file_id
    bucket.delete(oid)


def delete_files_by_notebook(bucket: GridFSBucket, db, notebook_id) -> int:
    """
    Delete all GridFS files for sources belonging to a notebook.
    Returns the count of deleted files.
    """
    oid = ObjectId(notebook_id) if not isinstance(notebook_id, ObjectId) else notebook_id
    sources = db.sources.find({"notebook_id": oid}, {"gridfs_file_id": 1})
    count = 0
    for source in sources:
        file_id = source.get("gridfs_file_id")
        if file_id:
            try:
                bucket.delete(file_id)
                count += 1
            except Exception:
                pass
    return count
