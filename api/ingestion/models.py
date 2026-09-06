from dataclasses import dataclass, field
from typing import Literal


Modality = Literal["text", "image", "table"]


@dataclass(slots=True)
class Asset:
    """An extracted visual asset held in memory for the duration of ingestion."""

    asset_id: str
    modality: Modality
    media_type: str
    data: bytes
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    caption: str | None = None


@dataclass(slots=True)
class MultimodalChunk:
    """Normalized text/visual unit that can be indexed by the text RAG pipeline."""

    content: str
    modality: Modality
    metadata: dict[str, object] = field(default_factory=dict)
    asset: Asset | None = None
