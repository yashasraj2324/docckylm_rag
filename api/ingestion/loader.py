import pypandoc
from langchain_core.documents import Document
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from markitdown import MarkItDown


def load_pdf(pdf_path):
    loader = PyMuPDF4LLMLoader(pdf_path)
    docs = loader.load()
    return docs


def load_docx(docx_path):
    try:
        text = pypandoc.convert_file(docx_path, "markdown")
    except OSError:
        # Pandoc not installed — try downloading (works locally, fails on serverless)
        print("Pandoc not found. Attempting to download...")
        try:
            pypandoc.download_pandoc()
            text = pypandoc.convert_file(docx_path, "markdown")
        except Exception as download_err:
            raise RuntimeError(
                "Pandoc is not installed and could not be downloaded. "
                "Install it with: apt-get install pandoc  (or pip install pypandoc-binary)"
            ) from download_err

    return [Document(page_content=text, metadata={"source": docx_path})]


def load_pptx(pptx_path):
    md = MarkItDown()
    result = md.convert(pptx_path)
    return [Document(page_content=result.text_content, metadata={"source": pptx_path})]
