"""
Core RAG retrieval + QA pipeline.

Handles:
  - Dense retrieval from Qdrant (k=12) filtered by notebook
  - NVIDIA reranker (top_n=5)
  - Citation formatting with page numbers
  - Multi-turn conversation history injection
  - Streaming answer generation
"""

from retrieval.reranker import rerank_documents
from vectorstore.qdrant_db import (
    ensure_payload_indexes,
    get_vectorstore,
    notebook_filter,
)

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

    if page is not None:
        return f"{file_name} — Page {page}"
    return file_name


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


def prepare_answer(embedding_model, query, notebook_id, history=None):
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

    reranked_docs = rerank_documents(query, docs)

    if not reranked_docs:
        return "", [], "", False

    context = "\n\n".join([doc.page_content for doc in reranked_docs])

    citations = [_format_citation(doc) for doc in reranked_docs]

    # Build conversation history block for multi-turn context
    history_block = _format_history(history)

    if history_block:
        prompt = f"""{SYSTEM_PROMPT}

Conversation so far:
{history_block}

Context from sources:
{context}

Question: {query}

Answer:"""
    else:
        prompt = f"""{SYSTEM_PROMPT}

Context from sources:
{context}

Question: {query}

Answer:"""

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
