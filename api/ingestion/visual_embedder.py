import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ingestion.models import Asset


DEFAULT_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
DEFAULT_TIMEOUT = 10
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
INDEX_ATTEMPTS = 3
DEFAULT_INDEX_TIMEOUT = 60


def _request_embedding(content, attempts=1, timeout=None):
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
    if timeout is None:
        timeout = int(os.getenv("OPENROUTER_EMBEDDING_TIMEOUT", str(DEFAULT_TIMEOUT)))
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read())
            return body["data"][0]["embedding"]
        except HTTPError as error:
            if error.code not in RETRYABLE_STATUS or attempt == attempts:
                raise
            time.sleep(2**attempt)  # transient provider error: back off and retry
        except (URLError, TimeoutError):  # socket timeouts / connection resets
            if attempt == attempts:
                raise
            time.sleep(2**attempt)


def embed_asset(asset: Asset) -> list[float]:
    encoded = base64.b64encode(asset.data).decode("ascii")
    # OpenRouter's multimodal embeddings take one object per input with a
    # `content` list; a flat list of parts is rejected with HTTP 400.
    # An empty text part is rejected (min length 1), and captions are empty when
    # vision captioning fails, so only send the text part when there is a caption.
    parts = []
    if (asset.caption or "").strip():
        parts.append({"type": "text", "text": asset.caption})
    parts.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:{asset.media_type};base64,{encoded}"},
        }
    )
    # Indexing is not latency-bound like query embedding, so ride out transient 5xx/429.
    timeout = int(os.getenv("OPENROUTER_INDEX_TIMEOUT", str(DEFAULT_INDEX_TIMEOUT)))
    return _request_embedding([{"content": parts}], attempts=INDEX_ATTEMPTS, timeout=timeout)


def embed_query(query: str) -> list[float]:
    return _request_embedding(query)
