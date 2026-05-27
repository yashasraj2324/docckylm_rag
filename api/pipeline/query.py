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


def prepare_answer(embedding_model, query, notebook_id):
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

    citations = []
    for doc in reranked_docs:
        citations.append(
            f"{doc.metadata.get('file_name') or doc.metadata.get('source')} "
            f"Page {doc.metadata.get('page')}"
        )

    prompt = f"""{SYSTEM_PROMPT}

Context: {context}

Question: {query}

Answer:"""

    return prompt, citations, context, True


def ask(chat_model, embedding_model, query, notebook_id):
    prompt, citations, _context, _success = prepare_answer(
        embedding_model, query, notebook_id
    )

    response = chat_model.invoke(prompt)

    return {"answer": response.content, "sources": citations}


def stream_answer(chat_model, prompt):
    for chunk in chat_model.stream(prompt):
        content = getattr(chunk, "content", "")
        if content:
            yield content
