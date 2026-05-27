from typing import Any, cast

from supabase import Client


def list_notebooks(client: Client, user_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("notebooks")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return cast(list[dict[str, Any]], response.data or [])


def create_notebook(
    client: Client, user_id: str, title: str = "Untitled notebook"
) -> dict[str, Any]:
    response = (
        client.table("notebooks")
        .insert(
            {
                "user_id": user_id,
                "title": title.strip() or "Untitled notebook",
            }
        )
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def rename_notebook(
    client: Client, user_id: str, notebook_id: str, title: str
) -> dict[str, Any]:
    response = (
        client.table("notebooks")
        .update({"title": title.strip() or "Untitled notebook"})
        .eq("id", notebook_id)
        .eq("user_id", user_id)
        .execute()
    )
    return cast(dict[str, Any], response.data[0])


def delete_notebook_rows(client: Client, user_id: str, notebook_id: str) -> None:
    (
        client.table("notebooks")
        .delete()
        .eq("id", notebook_id)
        .eq("user_id", user_id)
        .execute()
    )
