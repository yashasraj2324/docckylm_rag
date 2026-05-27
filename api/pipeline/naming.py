import json

from llm.chat_model import get_chat_model
from vectorstore.qdrant_db import scroll_notebook

SYSTEM_PROMPT = """You are an academic study assistant organizing a student's notes.
You will be provided with a few snippets extracted from the user's uploaded documents.
Based on this content, generate a short, descriptive title (2 to 5 words) for their notebook.
For example: "Biology 101 - Cell Structure" or "Machine Learning Basics".

Return ONLY the title as a raw JSON string. Do not wrap it in markdown.
Example:
"Advanced Quantum Physics"
"""


def generate_notebook_title(notebook_id: str) -> str:
    import time

    time.sleep(2)  # Give Qdrant a moment to make the ingested points searchable
    records = scroll_notebook(notebook_id, limit=5)
    docs = []
    for record in records:
        content = (record.payload or {}).get("page_content", "")
        if content:
            docs.append(content)

    if not docs:
        print("Warning: No docs found in Qdrant for auto-naming. Falling back.")
        return "Untitled notebook"

    context = "\n\n".join(docs)[:5000]

    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nGenerate the title now."

    chat_model = get_chat_model()
    response = chat_model.invoke(prompt)
    content = response.content.strip()

    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        title = json.loads(content)
        if isinstance(title, str):
            return title
    except Exception:
        # If it failed to parse as JSON string, maybe they just returned raw text
        if content.startswith('"') and content.endswith('"'):
            return content[1:-1]
        return content

    return "Untitled notebook"
