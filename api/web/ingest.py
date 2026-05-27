from ingestion.splitter import split_documents
from vectorstore.qdrant_db import ensure_payload_indexes, ingest_documents
from web.loader import load_search, load_url


def ingest_web_url(embedding_model, url, notebook_id, source_id):
    ensure_payload_indexes()
    docs = load_url(url)
    chunks = split_documents(docs, url, notebook_id, source_id)
    ingest_documents(chunks, embedding_model)


def ingest_web_search(embedding_model, query, notebook_id, source_id):
    ensure_payload_indexes()
    docs = load_search(query)
    chunks = split_documents(docs, f"Search: {query}", notebook_id, source_id)
    ingest_documents(chunks, embedding_model)


def ingest_parsed_search_result(embedding_model, result_dict, notebook_id, source_id):
    from langchain_core.documents import Document

    ensure_payload_indexes()
    doc = Document(
        page_content=result_dict["content"],
        metadata={"source": result_dict["url"], "title": result_dict["title"]},
    )
    chunks = split_documents([doc], result_dict["url"], notebook_id, source_id)
    ingest_documents(chunks, embedding_model)
