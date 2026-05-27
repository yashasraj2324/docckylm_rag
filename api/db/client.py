import os
import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_BUCKET = "notebook-sources"


def normalize_supabase_uri(uri: str) -> str:
    uri = uri.strip().lstrip("=")
    parsed = urlparse(uri)

    if parsed.scheme in {"http", "https"}:
        return uri

    if parsed.scheme in {"postgres", "postgresql"}:
        host = parsed.hostname or ""
        if host.startswith("db.") and host.endswith(".supabase.co"):
            project_ref = host.removeprefix("db.").removesuffix(".supabase.co")
            return f"https://{project_ref}.supabase.co"

    raise RuntimeError(
        "SUPABASE_URI must be either https://<project-ref>.supabase.co "
        "or a Supabase Postgres URI like "
        "postgresql://...@db.<project-ref>.supabase.co:5432/postgres."
    )


def safe_file_name(file_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", Path(file_name).name)


def build_client() -> tuple[Client, str, str, str]:
    """
    Reads env vars, validates them, and returns:
        (supabase_client, url, bucket, user_id)
    """
    raw_uri = os.getenv("SUPABASE_URI", "").strip()
    url = normalize_supabase_uri(raw_uri) if raw_uri else ""
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", DEFAULT_BUCKET).strip()
    user_id = os.getenv("DEMO_USER_ID", "").strip()

    missing = []
    if not url:
        missing.append("SUPABASE_URI")
    if not service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        raise RuntimeError(
            f"Missing Supabase config in rag/.env: {', '.join(missing)}."
        )

    if not user_id:
        raise RuntimeError(
            "DEMO_USER_ID must be set in rag/.env. Use a fixed UUID "
            "for this single-user demo."
        )

    try:
        UUID(user_id)
    except ValueError as exc:
        raise RuntimeError(
            "DEMO_USER_ID must be a valid UUID. Generate one with: "
            'python -c "import uuid; print(uuid.uuid4())"'
        ) from exc

    client: Client = create_client(
        url,
        service_role_key,
        options=SyncClientOptions(
            postgrest_client_timeout=300,
            storage_client_timeout=600,
            function_client_timeout=120,
        ),
    )

    return client, url, bucket, user_id
