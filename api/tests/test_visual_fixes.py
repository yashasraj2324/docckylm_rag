"""Regression tests for the visual-asset path (offline)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from ingestion.extractor import _image_media_type, load_asset  # noqa: E402
from ingestion.models import Asset  # noqa: E402
from pipeline import query  # noqa: E402


def test_media_type_comes_from_pymupdf_ext_not_mime():
    assert _image_media_type({"ext": "jpeg"}) == "image/jpeg"
    assert _image_media_type({"ext": "JPG"}) == "image/jpeg"
    assert _image_media_type({"ext": "png"}) == "image/png"
    assert _image_media_type({"mime": "image/webp", "ext": "png"}) == "image/webp"
    assert _image_media_type({}) == "image/png"  # unknown -> PyMuPDF's re-encode default


@pytest.mark.skipif(
    not (API_DIR / "evals" / "1706.03762v7.pdf").exists(), reason="reference PDF not fetched"
)
def test_load_asset_does_not_need_a_mime_key():
    pdf = (API_DIR / "evals" / "1706.03762v7.pdf").read_bytes()
    asset = load_asset(pdf, "1706.03762v7.pdf", "page-3-image-1")  # raised KeyError: 'mime'
    assert asset.media_type.startswith("image/") and asset.data


def test_prompt_image_uses_a_valid_data_uri(monkeypatch):
    doc = Document(
        page_content="Figure 1",
        metadata={"asset_id": "page-3-image-1", "source_id": "s1", "page": 3, "file_name": "a.pdf"},
    )
    monkeypatch.setattr(query, "ensure_payload_indexes", lambda: None)
    monkeypatch.setattr(query, "_visual_retrieval_enabled", lambda: False)
    monkeypatch.setattr(query, "rerank_documents", lambda q, docs: docs)

    class _Retriever:
        def invoke(self, q):
            return [doc]

    class _Store:
        def as_retriever(self, **kw):
            return _Retriever()

    monkeypatch.setattr(query, "get_vectorstore", lambda emb: _Store())
    loader = lambda source_id, asset_id: Asset(asset_id, "image", "image/png", b"\x89PNG", 3)
    prompt, *_ = query.prepare_answer(None, "q", "nb", asset_loader=loader)
    url = prompt[0]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,") and "base64:" not in url


def test_asset_embedding_payload_is_one_object_with_a_content_list(monkeypatch):
    from ingestion import visual_embedder

    seen = {}
    monkeypatch.setattr(visual_embedder, "_request_embedding", lambda content, **kw: seen.setdefault("c", content) and [0.0])
    visual_embedder.embed_asset(Asset("page-1-image-1", "image", "image/png", b"\x89PNG", 1, caption="Figure 1"))
    (item,) = seen["c"]  # exactly one input object, not a flat list of parts
    assert [p["type"] for p in item["content"]] == ["text", "image_url"]
    assert item["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_asset_embedding_omits_empty_caption(monkeypatch):
    from ingestion import visual_embedder

    seen = {}
    monkeypatch.setattr(visual_embedder, "_request_embedding", lambda content, **kw: seen.setdefault("c", content) and [0.0])
    visual_embedder.embed_asset(Asset("page-1-image-1", "image", "image/png", b"\x89PNG", 1, caption=""))
    assert [p["type"] for p in seen["c"][0]["content"]] == ["image_url"]  # no empty text part


def test_asset_embedding_retries_transient_errors_but_not_client_errors(monkeypatch):
    from urllib.error import HTTPError

    from ingestion import visual_embedder

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(visual_embedder.time, "sleep", lambda s: None)

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"data": [{"embedding": [0.1, 0.2]}]}'

    def flaky(codes):
        calls = iter(codes)
        def fake(request, timeout):
            code = next(calls)
            if code == 200:
                return _Resp()
            raise HTTPError("u", code, "err", {}, None)
        return fake

    monkeypatch.setattr(visual_embedder, "urlopen", flaky([502, 200]))
    asset = Asset("page-1-image-1", "image", "image/png", b"\x89PNG", 1)
    assert visual_embedder.embed_asset(asset) == [0.1, 0.2]  # 502 then success

    monkeypatch.setattr(visual_embedder, "urlopen", flaky([400, 200]))
    with pytest.raises(HTTPError):  # a 400 is a bug in the request; do not retry
        visual_embedder.embed_asset(asset)

    monkeypatch.setattr(visual_embedder, "urlopen", flaky([502]))
    with pytest.raises(HTTPError):  # query-time embedding stays single-attempt
        visual_embedder.embed_query("q")


class _FakeClient:
    def __init__(self):
        self.upserted = []
        self.queried = None

    def collection_exists(self, name): return True
    def create_payload_index(self, **kw): pass
    def upsert(self, collection_name, points): self.upserted += points

    def query_points(self, **kw):
        self.queried = kw

        class _R:
            points = []

        return _R()


def test_visual_search_uses_query_points(monkeypatch):
    from vectorstore import visual_qdrant as vq

    client = _FakeClient()
    monkeypatch.setattr(vq, "_get_client", lambda: client)
    monkeypatch.setattr(vq, "_collection_name", lambda: "c_visual")
    monkeypatch.setattr(vq, "embed_query", lambda q: [0.1, 0.2])
    assert vq.search_assets("q", "nb") == []  # qdrant-client >= 1.16 has no .search()
    assert client.queried["query"] == [0.1, 0.2] and client.queried["collection_name"] == "c_visual"


def test_visual_points_carry_file_name_for_citations(monkeypatch):
    from ingestion.models import MultimodalChunk
    from vectorstore import visual_qdrant as vq

    client = _FakeClient()
    monkeypatch.setattr(vq, "_get_client", lambda: client)
    monkeypatch.setattr(vq, "_collection_name", lambda: "c_visual")
    monkeypatch.setattr(vq, "_collection_ready", True)
    monkeypatch.setattr(vq, "embed_asset", lambda a: [0.1, 0.2])
    asset = Asset("page-3-image-1", "image", "image/png", b"\x89PNG", 3)
    chunk = MultimodalChunk(content="Figure", modality="image", metadata={"page": 3}, asset=asset)
    vq.upsert_assets([chunk], "nb", "s1", "paper.pdf")
    meta = client.upserted[0].payload["metadata"]
    assert meta["file_name"] == "paper.pdf" and meta["page"] == 3


def test_asset_embedding_retries_timeouts_with_a_longer_index_timeout(monkeypatch):
    from ingestion import visual_embedder

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(visual_embedder.time, "sleep", lambda s: None)
    timeouts = []

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"data": [{"embedding": [0.5]}]}'

    outcomes = iter([TimeoutError("The read operation timed out"), "ok"])

    def fake(request, timeout):
        timeouts.append(timeout)
        o = next(outcomes)
        if isinstance(o, Exception):
            raise o
        return _Resp()

    monkeypatch.setattr(visual_embedder, "urlopen", fake)
    asset = Asset("page-1-image-1", "image", "image/png", b"\x89PNG", 1)
    assert visual_embedder.embed_asset(asset) == [0.5]
    assert timeouts == [60, 60]  # indexing is not bound by the 10s query timeout
