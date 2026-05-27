import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


import threading

_local = threading.local()


def get_chat_model():
    if not hasattr(_local, "chat_model"):
        _local.chat_model = ChatNVIDIA(
            model=os.getenv("NVIDIA_CHAT_MODEL", "meta/llama-3.1-8b-instruct"),
            api_key=os.getenv("NVIDIA_API_KEY"),
        )
    return _local.chat_model
