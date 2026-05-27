import os
import socket
import threading
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

_local = threading.local()

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "notebook_lm").strip()
_DNS_PATCHED = False
_PAYLOAD_INDEXES_READY = False


def _patch_qdrant_dns(hostname, ip_address):
    global _DNS_PATCHED

    if _DNS_PATCHED or not hostname or not ip_address:
        return

    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host, *args, **kwargs):
        if host == hostname:
            return original_getaddrinfo(ip_address, *args, **kwargs)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo
    _DNS_PATCHED = True


def _qdrant_config():
    url = os.getenv("QDRANT_URL", "").strip()
    api_key = os.getenv("QDRANT_API_KEY", "").strip()
    resolved_ip = os.getenv("QDRANT_RESOLVED_IP", "").strip()
    timeout = int(os.getenv("QDRANT_TIMEOUT", "120").strip())

    if not url:
        raise RuntimeError(
            "QDRANT_URL is not set. Add your Qdrant Cloud cluster URL " "to rag/.env."
        )

    _patch_qdrant_dns(urlparse(url).hostname, resolved_ip)

    return {
        "url": url,
        "api_key": api_key or None,
        "collection_name": COLLECTION_NAME,
        "check_compatibility": False,
        "timeout": timeout,
    }


def _get_client():
    if not hasattr(_local, "qdrant_client"):
        cfg = _qdrant_config()
        _local.qdrant_client = QdrantClient(
            url=cfg["url"], api_key=cfg["api_key"], timeout=cfg["timeout"]
        )
    return _local.qdrant_client


def get_vectorstore(embedding_model):
    if not hasattr(_local, "qdrant_vectorstore"):
        cfg = _qdrant_config()
        _local.qdrant_vectorstore = QdrantVectorStore.from_existing_collection(
            embedding=embedding_model, **cfg
        )
    return _local.qdrant_vectorstore


def ingest_documents(chunks, embedding_model):
    batch_size = int(os.getenv("QDRANT_BATCH_SIZE", "8").strip())

    vectorstore = QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embedding_model,
        batch_size=batch_size,
        **_qdrant_config()
    )

    return vectorstore


def notebook_filter(notebook_id, source_ids=None):
    must_conditions = [
        models.FieldCondition(
            key="metadata.notebook_id", match=models.MatchValue(value=notebook_id)
        )
    ]
    if source_ids:
        must_conditions.append(
            models.FieldCondition(
                key="metadata.source_id", match=models.MatchAny(any=source_ids)
            )
        )
    return models.Filter(must=must_conditions)


def source_filter(source_id):
    return models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.source_id", match=models.MatchValue(value=source_id)
            )
        ]
    )


def _get_client():
    config = _qdrant_config()
    return QdrantClient(
        url=config["url"],
        api_key=config["api_key"],
        timeout=config["timeout"],
        check_compatibility=config["check_compatibility"],
    )


def ensure_payload_indexes():
    global _PAYLOAD_INDEXES_READY

    if _PAYLOAD_INDEXES_READY:
        return

    client = _get_client()
    uuid_index = models.UuidIndexParams(type=models.UuidIndexType.UUID)

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="metadata.notebook_id",
        field_schema=uuid_index,
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="metadata.source_id",
        field_schema=uuid_index,
    )

    _PAYLOAD_INDEXES_READY = True


def delete_by_notebook(notebook_id):
    client = _get_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(filter=notebook_filter(notebook_id)),
    )


def scroll_notebook(notebook_id, limit=500, source_ids=None):
    client = _get_client()
    records, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=notebook_filter(notebook_id, source_ids),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return records


def delete_by_source(source_id):
    client = _get_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(filter=source_filter(source_id)),
    )
