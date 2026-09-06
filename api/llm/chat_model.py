import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_local = threading.local()


def get_chat_model():
    if not hasattr(_local, "chat_model"):
        _local.chat_model = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            azure_deployment=os.getenv(
                "AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini"
            ),
        )
    return _local.chat_model
