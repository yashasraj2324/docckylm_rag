from langchain_text_splitters import MarkdownTextSplitter


def split_documents(docs, original_file_name, notebook_id, source_id):

    splitter = MarkdownTextSplitter(chunk_size=700, chunk_overlap=150)

    chunks = splitter.split_documents(docs)

    for i, chunk in enumerate(chunks):

        chunk.metadata["chunk_id"] = i

        chunk.metadata["source"] = original_file_name
        chunk.metadata["file_name"] = original_file_name
        chunk.metadata["notebook_id"] = notebook_id
        chunk.metadata["source_id"] = source_id

    return chunks
