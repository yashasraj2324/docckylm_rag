import json
import re

from vectorstore.qdrant_db import (
    ensure_payload_indexes,
    get_vectorstore,
    notebook_filter,
    scroll_notebook,
)

SYSTEM_PROMPT = """You are an academic study assistant creating flashcards for memorization.
You will be provided with some context extracted from the user's documents.

## Guidelines
- Extract key facts, definitions, or concepts.
- The question should be clear and specific.
- The answer must be short (preferably 1-15 words) for easy memorization.
- Generate EXACTLY {num_cards} flashcards.
- Adjust the content to a "{difficulty}" difficulty level.

## Output Format
You MUST return your answer as a raw JSON object containing a "title" string and a "cards" array of objects, with no additional text or markdown formatting.
Do not wrap it in ```json blocks. Just the object.

Example:
{{
  "title": "World Capitals and Geography",
  "cards": [
    {{
      "question": "What is the capital of France?",
      "answer": "Paris"
    }}
  ]
}}
"""

import random


def generate_flashcards(
    chat_model,
    embedding_model,
    notebook_id,
    topic,
    difficulty,
    num_cards,
    source_ids=None,
):
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
        # Randomly sample up to 10 chunks to ensure varied flashcards
        docs = random.sample(all_docs, min(len(all_docs), 10))
    else:
        # Retrieve random chunks from the notebook
        records = scroll_notebook(
            notebook_id, limit=100, source_ids=source_ids
        )  # Fetch up to 100 chunks

        # Qdrant scroll returns records, we extract payload text
        class DummyDoc:
            def __init__(self, page_content):
                self.page_content = page_content

        # Randomly sample up to 20 records
        sampled_records = random.sample(records, min(len(records), 20))
        for record in sampled_records:
            content = (record.payload or {}).get("page_content", "")
            if content:
                docs.append(DummyDoc(content))

    if not docs:
        return []

    context = "\n\n".join([doc.page_content for doc in docs])

    # Truncate context if it's insanely long to avoid max token issues
    context = context[:20000]

    prompt = f"""{SYSTEM_PROMPT.format(num_cards=num_cards, difficulty=difficulty)}

Context: {context}

Generate {num_cards} flashcards now as a JSON array."""

    response = chat_model.invoke(prompt)
    content = response.content.strip()

    # Clean up markdown if the LLM still provided it
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    title = "General Study"
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            flashcards = data.get("cards", [])
            title = data.get("title", "General Study")
        else:
            flashcards = []
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from LLM: {content}")
        # Try to find a JSON object via regex
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    flashcards = data.get("cards", [])
                    title = data.get("title", "General Study")
                else:
                    flashcards = []
            except json.JSONDecodeError:
                flashcards = []
        else:
            flashcards = []

    # Ensure the correct format
    valid_cards = []
    if isinstance(flashcards, list):
        for card in flashcards:
            if isinstance(card, dict) and "question" in card and "answer" in card:
                valid_cards.append(
                    {"question": card["question"], "answer": card["answer"]}
                )

    return {"title": title, "flashcards": valid_cards}
