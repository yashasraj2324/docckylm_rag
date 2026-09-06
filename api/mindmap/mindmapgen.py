import json
import os
import random

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from vectorstore.qdrant_db import (
    ensure_payload_indexes,
    get_vectorstore,
    notebook_filter,
    scroll_notebook,
)

MINDMAP_SYSTEM_PROMPT = """You are an expert educational content structurer. 
Your task is to analyze the provided source material and extract a highly structured, hierarchical Mind Map of the core concepts.

CRITICAL INSTRUCTIONS:
1. You must output ONLY valid, strictly well-formed JSON.
2. Do not include markdown code blocks (e.g. ```json) in your response, just the raw JSON object.
3. The root object MUST follow this exact schema:
{
  "name": "The main topic or central concept",
  "children": [
    {
      "name": "A major subtopic",
      "children": [
        {
          "name": "A detailed point or sub-subtopic",
          "children": []
        }
      ]
    }
  ]
}
4. Keep node names concise (1-5 words).
5. Ensure a logical hierarchy (Root -> Major Topics -> Subtopics).
6. The mind map should have a maximum depth of 2 or 3 levels to keep it concise and fast to generate.
7. The language must match the user's requested language.
"""

def build_mindmap_prompt(topic, context, language="English"):
    return f"""Topic / Focus: {topic}
Target Language: {language}

Source Material:
{context}

Please generate the complete, hierarchical mind map JSON based ONLY on the source material provided above. 
CRITICAL REQUIREMENT: Output strictly valid JSON. Do not output anything else.
"""


class DummyDoc:
    """Lightweight wrapper for page content from Qdrant records."""
    def __init__(self, page_content):
        self.page_content = page_content


def generate_mindmap_json(
    embedding_model, notebook_id, topic=None, language="English", source_ids=None
):
    """
    Retrieves context from Qdrant and generates a mindmap JSON structure using the chat model.
    """
    ensure_payload_indexes()

    azure_model = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_deployment=os.getenv(
            "AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini"
        ),
    )

    docs = []
    if topic and topic.strip() and topic != "Format: Deep Dive.":
        # Retrieve based on topic
        vectorstore = get_vectorstore(embedding_model)
        retriever = vectorstore.as_retriever(
            search_kwargs={"k": 8, "filter": notebook_filter(notebook_id, source_ids)}
        )
        all_docs = retriever.invoke(topic)
        if not all_docs:
            raise ValueError(
                "No source material found in the selected sources to generate a mind map."
            )
        docs = random.sample(all_docs, min(len(all_docs), 4))
    else:
        # Retrieve random chunks from the notebook
        records = scroll_notebook(notebook_id, limit=50, source_ids=source_ids)

        sampled_records = random.sample(records, min(len(records), 4))
        for record in sampled_records:
            content = (record.payload or {}).get("page_content", "")
            if content:
                docs.append(DummyDoc(content))

    context = "\n\n---\n\n".join([d.page_content for d in docs])

    if not context.strip():
        raise ValueError(
            "No source material found in the selected sources to generate a mind map."
        )

    prompt_text = build_mindmap_prompt(
        topic=topic or "General Overview", context=context, language=language
    )

    response = azure_model.invoke(
        [
            SystemMessage(content=MINDMAP_SYSTEM_PROMPT),
            HumanMessage(content=prompt_text),
        ]
    )

    content = response.content.strip()

    # Clean up markdown code blocks if the LLM ignored instructions
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    return json.loads(content.strip())
