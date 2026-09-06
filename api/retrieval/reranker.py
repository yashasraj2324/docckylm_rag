import os
from pathlib import Path

from dotenv import load_dotenv
import logfire
from langchain_nvidia_ai_endpoints import NVIDIARerank

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def rerank_documents(query, docs):
    if not docs:
        return docs

    model = os.getenv(
        "NVIDIA_RERANK_MODEL", "nvidia/llama-nemotron-rerank-1b-v2"
    ).strip()

    reranker = NVIDIARerank(model=model, api_key=os.getenv("NVIDIA_API_KEY"), top_n=5)

    with logfire.span("rag.reranker", model=model, candidate_count=len(docs)):
        try:
            ranked_docs = reranker.compress_documents(documents=docs, query=query)
        except Exception as err:
            logfire.warn("Reranking fallback triggered", error=str(err))
            return docs

    # Keep the dense retriever's strongest candidate available. The NVIDIA
    # reranker can over-prefer abstract prose or section headings and remove
    # the only factual chunk needed to answer a query.
    if docs and ranked_docs and docs[0] not in ranked_docs:
        ranked_docs = [*ranked_docs[:-1], docs[0]]

    return ranked_docs
