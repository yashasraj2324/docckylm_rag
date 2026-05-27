import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


import threading

_local = threading.local()


def get_embedding_model():
    if not hasattr(_local, "embedding_model"):
        _local.embedding_model = NVIDIAEmbeddings(
            model="nvidia/nv-embedqa-e5-v5", api_key=os.getenv("NVIDIA_API_KEY")
        )
    return _local.embedding_model
