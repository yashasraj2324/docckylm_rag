"""
Redis client for response caching and rate limiting.

Cache keys:
  rag:{notebook_id}:{hash(query)}  cached RAG answer + citations (TTL 1h)
  vision:{model}:{hash(image)}      cached visual description (TTL 24h)
  ocr:{hash(image)}                 cached RapidOCR text (TTL 24h)
  rl:{ip}:{endpoint}                rate limit counter (TTL = window)
"""

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import redis

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_pool = None


def get_redis():
    """Return a shared Redis client (thread-safe connection pool)."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
    return redis.Redis(connection_pool=_pool)


# Response Cache

def _cache_key(notebook_id: str, query: str) -> str:
    h = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"rag:{notebook_id}:{h}"


def get_cached_response(notebook_id: str, query: str):
    """Return cached (answer, citations) or None on miss."""
    r = get_redis()
    val = r.get(_cache_key(notebook_id, query))
    if val:
        return json.loads(val)
    return None


def set_cached_response(
    notebook_id: str, query: str, answer: str, citations: list, ttl: int = 3600
):
    """Store a RAG response in Redis."""
    r = get_redis()
    r.setex(
        _cache_key(notebook_id, query),
        ttl,
        json.dumps({"answer": answer, "citations": citations}),
    )


def _vision_cache_key(model: str, image_data: bytes) -> str:
    image_hash = hashlib.sha256(image_data).hexdigest()
    model_hash = hashlib.sha256(model.encode()).hexdigest()[:16]
    return f"vision:{model_hash}:{image_hash}"


def get_cached_vision_description(model: str, image_data: bytes):
    """Return a cached NVIDIA vision description or None on miss."""
    value = get_redis().get(_vision_cache_key(model, image_data))
    return value or None


def set_cached_vision_description(
    model: str, image_data: bytes, description: str, ttl: int = 86400
):
    """Cache a visual description independently of the source document."""
    get_redis().setex(
        _vision_cache_key(model, image_data),
        ttl,
        description,
    )


def get_cached_ocr_text(image_data: bytes):
    value = get_redis().get(f"ocr:{hashlib.sha256(image_data).hexdigest()}")
    return value or None


def set_cached_ocr_text(image_data: bytes, text: str, ttl: int = 86400):
    get_redis().setex(
        f"ocr:{hashlib.sha256(image_data).hexdigest()}",
        ttl,
        text,
    )


def invalidate_notebook_cache(notebook_id: str):
    """Delete all cached responses for a notebook (on source add/delete)."""
    r = get_redis()
    for key in r.scan_iter(f"rag:{notebook_id}:*"):
        r.delete(key)


# Rate Limiter

def check_rate_limit(ip: str, endpoint: str, limit: int, window: int) -> bool:
    """
    Sliding window counter. Returns True if allowed, False if rate-limited.
    """
    r = get_redis()
    key = f"rl:{ip}:{endpoint}"
    current = r.incr(key)
    if current == 1:
        r.expire(key, window)
    return current <= limit
