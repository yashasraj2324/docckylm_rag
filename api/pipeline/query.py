"""
Core RAG retrieval + QA pipeline.

Handles:
  - Dense retrieval from Qdrant (k=12) filtered by notebook
  - NVIDIA reranker (top_n=5)
  - Citation formatting with page numbers
  - Multi-turn conversation history injection
  - Streaming answer generation
"""

import base64

from retrieval.reranker import rerank_documents
from vectorstore.qdrant_db import (
    ensure_payload_indexes,
    get_vectorstore,
    notebook_filter,
)
from vectorstore.visual_qdrant import search_assets

SYSTEM_PROMPT = """You are an academic study assistant creating concise, well-formatted study notes. Base responses strictly on the provided context.

## Format Requirements
- Start with a brief 1-2 sentence summary
- Use short paragraphs (2-3 sentences max)
- Break up text with bullet points and subheadings
- Bold key terms for easy scanning
- Keep line length reasonable for mobile/narrow displays

## Content Guidelines
- Extract only information present in the context
- Use clear, direct language
- Organize logically with headers
- Include specific examples from the source
- State if information is insufficient

---"""

# Maximum number of prior messages to include as conversation context.
# Keeps the prompt within model limits while enabling multi-turn follow-ups.
MAX_HISTORY_MESSAGES = 10


def _format_citation(doc):
    """Build a human-readable citation string from document metadata."""
    file_name = doc.metadata.get("file_name") or doc.metadata.get("source", "Unknown")
    page = doc.metadata.get("page")

    citation = f"{file_name} — Page {page}" if page is not None else file_name
    asset_id = doc.metadata.get("asset_id")
    if not asset_id:
        return citation
    notebook_id = doc.metadata.get("notebook_id")
    source_id = doc.metadata.get("source_id")
    asset_url = (
        f"/api/python/notebooks/{notebook_id}/assets/{source_id}/{asset_id}"
        if notebook_id and source_id
        else ""
    )
    return f"{citation} — Asset {asset_id}{f' ({asset_url})' if asset_url else ''}"


def _format_history(history):
    """
    Format recent conversation history into a string suitable for prompt injection.

    Only the most recent MAX_HISTORY_MESSAGES are included (excluding the current
    user query, which is already part of the prompt).
    """
    if not history:
        return ""

    # Take the last N messages, excluding the most recent user message (the
    # current query) which is already in the prompt template.
    recent = history[-(MAX_HISTORY_MESSAGES + 1) : -1]
    if not recent:
        return ""

    lines = []
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")

    if not lines:
        return ""

    return "\n".join(lines)


def prepare_answer(
    embedding_model, query, notebook_id, history=None, asset_loader=None
):
    """
    Retrieve relevant context and build the LLM prompt.

    Args:
        embedding_model: NVIDIA embedding model instance.
        query: The user's question.
        notebook_id: The notebook to search within.
        history: Optional list of prior messages (dicts with 'role' and 'content')
                 for multi-turn conversation context.

    Returns:
        (prompt, citations, context, has_context) tuple.
    """
    ensure_payload_indexes()

    vectorstore = get_vectorstore(embedding_model)

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 12, "filter": notebook_filter(notebook_id)}
    )

    docs = retriever.invoke(query)
    try:
        docs.extend(search_assets(query, notebook_id))
    except Exception as error:
        print(f"[query] Visual retrieval skipped: {error}")

    reranked_docs = rerank_documents(query, docs)

    if not reranked_docs:
        return "", [], "", False

    context = "\n\n".join([doc.page_content for doc in reranked_docs])

    citations = [_format_citation(doc) for doc in reranked_docs]

    # Build conversation history block for multi-turn context
    history_block = _format_history(history)

    if history_block:
        prompt_text = f"""{SYSTEM_PROMPT}

Conversation so far:
{history_block}

Context from sources:
{context}

Question: {query}

Answer:"""
    else:
        prompt_text = f"""{SYSTEM_PROMPT}

Context from sources:
{context}

Question: {query}

Answer:"""

    visual_content = []
    if asset_loader:
        for doc in reranked_docs:
            asset_id = doc.metadata.get("asset_id")
            source_id = doc.metadata.get("source_id")
            if not asset_id or not source_id:
                continue
            try:
                asset = asset_loader(source_id, asset_id)
                visual_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{asset.media_type};base64:"
                                f"{base64.b64encode(asset.data).decode('ascii')}"
                            )
                        },
                    }
                )
            except Exception as error:
                print(f"[query] Visual asset skipped for {asset_id}: {error}")

    prompt = (
        [{"role": "user", "content": [{"type": "text", "text": prompt_text}] + visual_content}]
        if visual_content
        else prompt_text
    )

    return prompt, citations, context, True


def ask(chat_model, embedding_model, query, notebook_id, history=None):
    """Non-streaming query — returns the full answer and citations."""
    prompt, citations, _context, _success = prepare_answer(
        embedding_model, query, notebook_id, history=history
    )

    response = chat_model.invoke(prompt)

    return {"answer": response.content, "sources": citations}


def stream_answer(chat_model, prompt):
    """Yield answer tokens as they arrive from the LLM."""
    for chunk in chat_model.stream(prompt):
        content = getattr(chunk, "content", "")
        if content:
            yield content
