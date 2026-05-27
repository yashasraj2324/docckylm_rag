import uuid
from typing import Any


def list_podcasts(client, notebook_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("podcasts")
        .select("*")
        .eq("notebook_id", notebook_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


def save_podcast(
    client, notebook_id: str, audio_url: str, format: str, language: str
) -> dict[str, Any]:
    response = (
        client.table("podcasts")
        .insert(
            {
                "notebook_id": notebook_id,
                "audio_url": audio_url,
                "format": format,
                "language": language,
            }
        )
        .execute()
    )
    return response.data[0] if response.data else {}


def delete_podcast(client, podcast_id: str) -> None:
    client.table("podcasts").delete().eq("id", podcast_id).execute()


def upload_podcast_audio(client, user_id: str, notebook_id: str, data: bytes) -> str:
    """Uploads podcast audio to the 'podcasts' bucket and returns the public URL."""
    podcast_id = str(uuid.uuid4())
    path = f"{user_id}/{notebook_id}/{podcast_id}.mp3"

    res = client.storage.from_("podcasts").upload(
        path=path,
        file=data,
        file_options={"content-type": "audio/mpeg", "x-upsert": "true"},
    )

    # Get the public URL for the newly uploaded file
    public_url = client.storage.from_("podcasts").get_public_url(path)
    return public_url
