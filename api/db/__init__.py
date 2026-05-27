# Re-export SupabaseDB so existing code (`from supabase_db import SupabaseDB`)
# continues to work unchanged after renaming to supabase package.
from db.base import SupabaseDB

__all__ = ["SupabaseDB"]
