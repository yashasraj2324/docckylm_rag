"""
Redis client for response caching and rate limiting.

Cache keys:
  rag:{notebook_id}:{hash(query)}  cached RAG answer + citations (TTL 1h)
  emb:{hash(text)}                  cached embedding vector (TTL 24h)
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
