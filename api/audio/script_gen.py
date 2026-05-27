import random

from audio.prompt import PODCAST_SYSTEM_PROMPT, build_podcast_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from vectorstore.qdrant_db import (
    ensure_payload_indexes,
    get_vectorstore,
    notebook_filter,
    scroll_notebook,
)


def generate_podcast_script(
    chat_model,
    embedding_model,
    notebook_id,
    topic=None,
    language="English",
    format="Podcast",
    length="Short",
    source_ids=None,
):
    """
    Retrieves context from Qdrant and generates a podcast script using the chat model.
    """
    ensure_payload_indexes()

    docs = []
    if topic and topic.strip():
        # Retrieve based on topic
        vectorstore = get_vectorstore(embedding_model)
        retriever = vectorstore.as_retriever(
            search_kwargs={
                "k": 30,  # Fetch more chunks to allow randomization
                "filter": notebook_filter(notebook_id, source_ids),
            }
        )
        all_docs = retriever.invoke(topic)
        # Sample chunks for varied scripts
        docs = random.sample(all_docs, min(len(all_docs), 6))
    else:
        # Retrieve random chunks from the notebook
        records = scroll_notebook(notebook_id, limit=100, source_ids=source_ids)

        class DummyDoc:
            def __init__(self, page_content):
                self.page_content = page_content

        # Randomly sample up to 8 records
        sampled_records = random.sample(records, min(len(records), 8))
        for record in sampled_records:
            content = (record.payload or {}).get("page_content", "")
            if content:
                docs.append(DummyDoc(content))

    # Combine all retrieved context chunks into a single string
    context = "\n\n---\n\n".join([d.page_content for d in docs])

    if not context.strip():
        raise ValueError(
            "No source material found in the selected sources to generate a podcast."
        )

    # Build the specialized podcast prompt
    prompt_text = build_podcast_prompt(
        topic=topic or "General Overview",
        context=context,
        language=language,
        format=format,
        length=length,
    )

    # Invoke the LLM to write the script
    response = chat_model.invoke(
        [
            SystemMessage(content=PODCAST_SYSTEM_PROMPT),
            HumanMessage(content=prompt_text),
        ]
    )

    return response.content
