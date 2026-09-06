import base64
import json
import os
from urllib.request import Request, urlopen

from ingestion.models import Asset


DEFAULT_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"


def _request_embedding(content):
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload = json.dumps(
        {
            "model": os.getenv("OPENROUTER_EMBEDDING_MODEL", DEFAULT_MODEL),
            "input": content,
        }
    ).encode()
    request = Request(
        "https://openrouter.ai/api/v1/embeddings",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        body = json.loads(response.read())
    return body["data"][0]["embedding"]


def embed_asset(asset: Asset) -> list[float]:
    encoded = base64.b64encode(asset.data).decode("ascii")
    return _request_embedding(
        [
            {"type": "text", "text": asset.caption or ""},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{asset.media_type};base64,{encoded}"},
            },
        ]
    )


def embed_query(query: str) -> list[float]:
    return _request_embedding(query)
