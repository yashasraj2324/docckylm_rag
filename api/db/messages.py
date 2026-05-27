from typing import Any, cast

from supabase import Client


def save_message(
    client: Client,
    notebook_id: str,
    role: str,
    content: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    response = (
        client.table("messages")
        .insert(
            {
                "notebook_id": notebook_id,
                "role": role,
                "content": content,
                "sources_json": sources or [],
            }
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def list_messages(client: Client, notebook_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("messages")
        .select("*")
        .eq("notebook_id", notebook_id)
        .order("created_at", desc=False)
        .execute()
    )
    rows = cast(list[dict[str, Any]], response.data or [])
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "sources": row.get("sources_json") or [],
        }
        for row in rows
    ]
