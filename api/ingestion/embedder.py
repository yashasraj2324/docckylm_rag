import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_local = threading.local()


def get_embedding_model():
    if not hasattr(_local, "embedding_model"):
        _local.embedding_model = AzureOpenAIEmbeddings(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            azure_deployment=os.getenv(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
            ),
        )
    return _local.embedding_model
