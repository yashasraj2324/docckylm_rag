"""
Telemetry and observability configuration using Pydantic Logfire.

Provides automatic instrumentation for:
- FastAPI (routes, middleware, request spans)
- Pydantic models & validation
- LangChain pipelines & chains (via OpenInference)
- OpenAI & Azure OpenAI calls
- PyMongo queries & operations
- Redis caching operations
- HTTP clients (httpx, requests)
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import logfire

load_dotenv(Path(__file__).resolve().parent / ".env")

_INITIALIZED = False


def init_telemetry(app=None):
    """
    Initialize Logfire and all supported instrumentations.
    
    `send_to_logfire="if-token-present"` ensures safe execution both locally
    (console/noop) and when a `LOGFIRE_TOKEN` is provided for cloud tracing.
    """
    global _INITIALIZED

    if not _INITIALIZED:
        logfire.configure(
            service_name=os.getenv("LOGFIRE_SERVICE_NAME", "ai-notebooks-api"),
            send_to_logfire="if-token-present",
            inspect_arguments=False,
        )


        # 1. Pydantic
        try:
            logfire.instrument_pydantic()
        except Exception as err:
            print(f"[telemetry] Pydantic instrumentation skipped: {err}")

        # 2. OpenAI / Azure OpenAI
        try:
            logfire.instrument_openai()
        except Exception as err:
            print(f"[telemetry] OpenAI instrumentation skipped: {err}")

        # 3. LangChain (via OpenInference OpenTelemetry integration)
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor
            LangChainInstrumentor().instrument()
        except Exception as err:
            print(f"[telemetry] LangChain instrumentation skipped: {err}")

        # 4. PyMongo
        try:
            logfire.instrument_pymongo()
        except Exception as err:
            print(f"[telemetry] PyMongo instrumentation skipped: {err}")

        # 5. Redis
        try:
            logfire.instrument_redis()
        except Exception as err:
            print(f"[telemetry] Redis instrumentation skipped: {err}")

        # 6. HTTP clients
        try:
            logfire.instrument_httpx()
        except Exception as err:
            print(f"[telemetry] HTTPX instrumentation skipped: {err}")

        try:
            logfire.instrument_requests()
        except Exception as err:
            print(f"[telemetry] Requests instrumentation skipped: {err}")

        _INITIALIZED = True

    # 7. FastAPI instrumentation (attached to app instance)
    if app is not None:
        try:
            logfire.instrument_fastapi(app)
        except Exception as err:
            print(f"[telemetry] FastAPI instrumentation skipped: {err}")
