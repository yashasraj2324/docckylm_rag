from ingestion.loader import load_docx, load_pdf, load_pptx
from ingestion.splitter import split_documents
from vectorstore.qdrant_db import ensure_payload_indexes, ingest_documents


def ingest(embedding_model, pdf_path, original_file_name, notebook_id, source_id):
    ensure_payload_indexes()

    if pdf_path.lower().endswith((".doc", ".docx")):
        docs = load_docx(pdf_path)
    elif pdf_path.lower().endswith(".pptx"):
        docs = load_pptx(pdf_path)
    else:
        docs = load_pdf(pdf_path)

    chunks = split_documents(docs, original_file_name, notebook_id, source_id)

    ingest_documents(chunks, embedding_model)
