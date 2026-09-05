# Re-export Database so `from db import Database` works.
from db.base import Database

__all__ = ["Database"]
