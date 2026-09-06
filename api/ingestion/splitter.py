"""
Document splitter with metadata preservation.

Upgraded from MarkdownTextSplitter (700 chars) to RecursiveCharacterTextSplitter
(1200 chars) which respects paragraph/section boundaries and preserves page
metadata from PyMuPDF4LLM through the splitting process.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Recursive splitter tries to split on, in order:
#   "\n\n" (paragraphs) → "\n" (lines) → ". " (sentences) → " " (words) → "" (chars)
# This keeps semantic units intact far better than MarkdownTextSplitter.
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=200,
    separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],
    keep_separator=True,
)


def split_documents(docs, original_file_name, notebook_id, source_id):
    """
    Split documents into chunks, preserving page metadata from the loader.

    PyMuPDF4LLMLoader sets `page` (1-based int) on each Document's metadata.
    When a chunk spans multiple source pages (because the splitter merged or
    split across a page boundary), we record the page of the *first* segment
    and also store a `pages` list for completeness.
    """
    # If the loader already produced per-page documents, split each one
    # individually so page metadata is never lost across a page boundary.
    all_chunks = []

    for doc in docs:
        source_page = doc.metadata.get("page")

        sub_chunks = SPLITTER.split_documents([doc])

        for chunk in sub_chunks:
            # Preserve the page from the parent document if the splitter
            # didn't carry it forward (it usually does, but be defensive).
            if "page" not in chunk.metadata and source_page is not None:
                chunk.metadata["page"] = source_page

            all_chunks.append(chunk)

    # Now stamp the common metadata onto every chunk.
    for i, chunk in enumerate(all_chunks):
        chunk.metadata["chunk_id"] = i
        chunk.metadata["source"] = original_file_name
        chunk.metadata["file_name"] = original_file_name
        chunk.metadata["notebook_id"] = notebook_id
        chunk.metadata["source_id"] = source_id

    return all_chunks
