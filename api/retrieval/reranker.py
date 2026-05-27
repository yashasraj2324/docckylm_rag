import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import NVIDIARerank

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def rerank_documents(query, docs):
    if not docs:
        return docs

    model = os.getenv(
        "NVIDIA_RERANK_MODEL", "nvidia/llama-nemotron-rerank-1b-v2"
    ).strip()

    reranker = NVIDIARerank(model=model, api_key=os.getenv("NVIDIA_API_KEY"), top_n=5)

    try:
        ranked_docs = reranker.compress_documents(documents=docs, query=query)
    except Exception:
        return docs

    return ranked_docs
