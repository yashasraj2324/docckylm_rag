import os
import warnings

from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings, NVIDIARerank
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from langchain_text_splitters import MarkdownTextSplitter

# Suppress all warnings
warnings.filterwarnings("ignore")
loader = PyMuPDF4LLMLoader(r"rag\ingestion\Lecture Material_HCI _Module 5.pdf")
docs = loader.load()


splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = splitter.split_documents(docs)

print(chunks[1])
