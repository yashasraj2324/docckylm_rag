from typing import Any


def list_mindmaps(client, notebook_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("mindmaps")
        .select("*")
        .eq("notebook_id", notebook_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


def save_mindmap(
    client, notebook_id: str, topic: str, data: dict[str, Any]
) -> dict[str, Any]:
    response = (
        client.table("mindmaps")
        .insert({"notebook_id": notebook_id, "topic": topic, "data": data})
        .execute()
    )
    return response.data[0] if response.data else {}


def delete_mindmap(client, mindmap_id: str) -> None:
    client.table("mindmaps").delete().eq("id", mindmap_id).execute()
