import os

import logfire

from ingestion.loader import load_docx, load_pdf, load_pptx
from ingestion.extractor import extract_multimodal_chunks, to_documents
from ingestion.splitter import split_documents
from vectorstore.qdrant_db import ensure_payload_indexes, ingest_documents
from vectorstore.visual_qdrant import upsert_assets


SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "docx",
    ".pptx": "pptx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}


def ingest(embedding_model, file_path, original_file_name, notebook_id, source_id):
    with logfire.span(
        "rag.ingest_source",
        file_name=original_file_name,
        source_id=source_id,
        notebook_id=notebook_id,
    ):
        extension = os.path.splitext(original_file_name or file_path)[1].lower()
        source_type = SUPPORTED_EXTENSIONS.get(extension)
        if source_type is None:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Unsupported source extension '{extension or '<none>'}'. "
                f"Supported extensions: {supported}"
            )

        with logfire.span("rag.load_file", source_type=source_type):
            if source_type in ("doc", "docx"):
                docs = load_docx(file_path)
            elif source_type == "pptx":
                docs = load_pptx(file_path)
            elif source_type == "image":
                docs = []
            else:
                docs = load_pdf(file_path)

        with logfire.span("rag.split_documents", doc_count=len(docs)):
            text_chunks = split_documents(
                docs, original_file_name, notebook_id, source_id
            )

        with logfire.span("rag.extract_multimodal"):
            multimodal_chunks = extract_multimodal_chunks(
                file_path, original_file_name, text_chunks
            )
            chunks = to_documents(
                multimodal_chunks, original_file_name, notebook_id, source_id
            )

        with logfire.span("rag.qdrant_ingest", chunk_count=len(chunks)):
            ensure_payload_indexes()
            ingest_documents(chunks, embedding_model)

        try:
            with logfire.span("rag.visual_upsert"):
                upsert_assets(multimodal_chunks, notebook_id, source_id)
        except Exception as error:
            print(f"[ingest] Visual indexing skipped: {error}")
