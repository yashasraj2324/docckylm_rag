from typing import Any, cast

from db.client import safe_file_name
from supabase import Client


def create_source(
    client: Client,
    notebook_id: str,
    source_id: str,
    file_name: str,
    storage_path: str,
    status: str = "indexing",
) -> dict[str, Any]:
    response = (
        client.table("sources")
        .insert(
            {
                "id": source_id,
                "notebook_id": notebook_id,
                "source_type": "pdf",
                "file_name": file_name,
                "storage_path": storage_path,
                "status": status,
            }
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def update_source_status(client: Client, source_id: str, status: str) -> None:
    (client.table("sources").update({"status": status}).eq("id", source_id).execute())


def list_sources(client: Client, notebook_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("sources")
        .select("*")
        .eq("notebook_id", notebook_id)
        .order("created_at", desc=False)
        .execute()
    )
    return cast(list[dict[str, Any]], response.data or [])


def delete_source_row(client: Client, source_id: str) -> None:
    (client.table("sources").delete().eq("id", source_id).execute())


def upload_pdf(
    client: Client,
    bucket: str,
    user_id: str,
    notebook_id: str,
    source_id: str,
    file_name: str,
    data: bytes,
) -> str:
    storage_path = (
        f"{user_id}/{notebook_id}/{source_id}/" f"{safe_file_name(file_name)}"
    )
    client.storage.from_(bucket).upload(
        storage_path,
        data,
        file_options={
            "content-type": "application/pdf",
            "upsert": "true",
        },
    )
    return storage_path


def delete_storage_paths(client: Client, bucket: str, storage_paths: list[str]) -> None:
    if storage_paths:
        client.storage.from_(bucket).remove(storage_paths)


def delete_storage_prefix(
    client: Client, bucket: str, user_id: str, notebook_id: str
) -> None:
    prefix = f"{user_id}/{notebook_id}"
    response = client.storage.from_(bucket).list(prefix)
    paths = [
        f"{prefix}/{item['name']}" for item in (response or []) if item.get("name")
    ]
    delete_storage_paths(client, bucket, paths)
