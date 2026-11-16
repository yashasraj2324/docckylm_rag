"""Typed inputs, metadata and outputs for the pydantic_evals RAG suite."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SourceRef(BaseModel, frozen=True):
    """A (file, page) pair. ``page=None`` means file-level only."""

    file: str
    page: int | None = None


class CaseInputs(BaseModel):
    question: str
    notebook_id: str


class CaseMetadata(BaseModel):
    category: Literal["factual", "summarization", "multi-hop", "visual", "adversarial"]
    expected_sources: list[SourceRef]
    expected_keywords: list[str] = []
    is_adversarial: bool = False


RefusalReason = Literal["no_context", "gate", "model"]


class RagOutput(BaseModel):
    answer: str
    refused: bool
    refusal_reason: RefusalReason | None = None
    # (file, page) per reranked document, in rank order.
    retrieved: list[SourceRef]
    # Citation strings exactly as the chat endpoint would emit them.
    citations: list[str]
    # The retrieved context text the LLM was given; judges read this.
    retrieved_context: str
