"""Shared dependencies for API route modules."""

from db import Database


_db_instance = None


def get_db() -> Database:
    """Return the lazily initialized database client."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
