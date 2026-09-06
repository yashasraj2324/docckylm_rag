import threading
import uuid

from qdrant_client.http import models

from ingestion.visual_embedder import embed_asset, embed_query
from vectorstore.qdrant_db import _get_client, _qdrant_config, notebook_filter


_collection_ready = False
_collection_lock = threading.Lock()


def _collection_name():
    return f"{_qdrant_config()['collection_name']}_visual"


def _ensure_collection(vector_size: int):
    global _collection_ready
    if _collection_ready:
        return
    with _collection_lock:
        if _collection_ready:
            return
        client = _get_client()
        name = _collection_name()
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        _collection_ready = True


def upsert_assets(chunks, notebook_id, source_id):
    client = _get_client()
    points = []
    for chunk in chunks:
        if not chunk.asset or chunk.modality != "image":
            continue
        try:
            vector = embed_asset(chunk.asset)
        except Exception as error:
            print(
                f"[visual-index] Asset skipped for {chunk.asset.asset_id}: {error}"
            )
            continue
        _ensure_collection(len(vector))
        payload = {
            "page_content": chunk.content,
            "metadata": {
                **chunk.metadata,
                "notebook_id": notebook_id,
                "source_id": source_id,
                "modality": "image",
            },
        }
        point_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{source_id}:{chunk.asset.asset_id}",
            )
        )
        points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
    if points:
        client.upsert(collection_name=_collection_name(), points=points)


def search_assets(query, notebook_id, limit=6):
    if not _get_client().collection_exists(_collection_name()):
        return []
    vector = embed_query(query)
    records = _get_client().search(
        collection_name=_collection_name(),
        query_vector=vector,
        query_filter=notebook_filter(notebook_id),
        limit=limit,
        with_payload=True,
    )
    from langchain_core.documents import Document

    return [
        Document(
            page_content=record.payload.get("page_content", ""),
            metadata=record.payload.get("metadata", {}),
        )
        for record in records
    ]


def delete_by_source(source_id):
    if not _get_client().collection_exists(_collection_name()):
        return
    _get_client().delete(
        collection_name=_collection_name(),
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.source_id",
                        match=models.MatchValue(value=source_id),
                    )
                ]
            )
        ),
    )


def delete_by_notebook(notebook_id):
    if not _get_client().collection_exists(_collection_name()):
        return
    _get_client().delete(
        collection_name=_collection_name(),
        points_selector=models.FilterSelector(
            filter=notebook_filter(notebook_id)
        ),
    )
