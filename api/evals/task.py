"""The eval task: runs the real RAG pipeline the way routes/chat.py does."""

from __future__ import annotations

import re

from evals.schemas import CaseInputs, RagOutput, SourceRef

# Mirrors the literal in routes/chat.py (guarded by tests/test_eval_harness.py).
NO_CONTEXT_MESSAGE = (
    "I couldn't find relevant information in your sources. Please add PDFs and try again."
)
_MODEL_REFUSAL_MARKER = "couldn't find relevant information"
_CITATION_RE = re.compile(r"^(?P<file>.+?)\s+—\s+Page\s+(?P<page>\d+)")


def parse_citation(citation: str) -> SourceRef:
    """Turn a ``_format_citation`` string into a (file, page) reference."""
    m = _CITATION_RE.match(citation)
    if m:
        return SourceRef(file=m.group("file").strip(), page=int(m.group("page")))
    return SourceRef(file=citation.split(" — ")[0].strip(), page=None)


def is_model_refusal(answer: str) -> bool:
    return _MODEL_REFUSAL_MARKER in answer.lower().replace("’", "'")


_db = None


def _resources():
    global _db
    from ingestion.embedder import get_embedding_model
    from llm.chat_model import get_chat_model
    from routes.dependencies import get_db

    if _db is None:
        _db = get_db()
    # Models are thread-local inside the pipeline modules, so fetch per call.
    return _db, get_chat_model(), get_embedding_model()


def run_rag(inputs: CaseInputs) -> RagOutput:
    """Same flow as ``chat_stream``: prepare -> support gate -> stream answer."""
    from ingestion.extractor import load_asset
    from pipeline.query import context_supports_query, prepare_answer, stream_answer

    db, chat_model, embedding_model = _resources()
    notebook_id = inputs.notebook_id

    def asset_loader(source_id, asset_id):
        source = next(s for s in db.list_sources(notebook_id) if s["id"] == source_id)
        return load_asset(
            db.download_source_file(source["gridfs_file_id"]),
            source["file_name"],
            asset_id,
        )

    prompt, citations, context, has_context = prepare_answer(
        embedding_model,
        inputs.question,
        notebook_id,
        history=None,
        asset_loader=asset_loader,
    )
    retrieved = [parse_citation(c) for c in citations]

    if not has_context:
        return RagOutput(
            answer=NO_CONTEXT_MESSAGE, refused=True, refusal_reason="no_context",
            retrieved=retrieved, citations=citations, retrieved_context=context,
        )
    if not context_supports_query(chat_model, inputs.question, context):
        return RagOutput(
            answer=NO_CONTEXT_MESSAGE, refused=True, refusal_reason="gate",
            retrieved=retrieved, citations=citations, retrieved_context=context,
        )

    answer = "".join(stream_answer(chat_model, prompt))
    refused = is_model_refusal(answer)
    return RagOutput(
        answer=answer, refused=refused, refusal_reason="model" if refused else None,
        retrieved=retrieved, citations=citations, retrieved_context=context,
    )
