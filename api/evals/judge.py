"""Judge-model construction. The judge must differ from the answer model."""

from __future__ import annotations

import os


class JudgeConfigError(RuntimeError):
    pass


def _norm(spec: str) -> str:
    return spec.strip().lower().removeprefix("azure:")


def generation_model_id() -> str:
    return os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini").strip()


def judge_model_spec() -> str:
    spec = os.getenv("EVAL_JUDGE_MODEL", "").strip()
    if not spec:
        raise JudgeConfigError(
            "EVAL_JUDGE_MODEL is not set. Set it to 'azure:<deployment>' or a "
            "pydantic-ai model string (e.g. 'anthropic:<model>'); it must differ "
            f"from the answer model ({generation_model_id()!r})."
        )
    if _norm(spec) == _norm(generation_model_id()):
        raise JudgeConfigError(
            f"EVAL_JUDGE_MODEL ({spec!r}) is the same as the answer-generating "
            f"model ({generation_model_id()!r}). Use a different model."
        )
    return spec


def build_judge_model():
    """Return a pydantic-ai model (or model string) for LLMJudge."""
    spec = judge_model_spec()
    if not spec.lower().startswith("azure:"):
        return spec
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.azure import AzureProvider

    return OpenAIChatModel(
        spec.split(":", 1)[1],
        provider=AzureProvider(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        ),
    )
