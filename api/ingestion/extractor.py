import base64
import os
from pathlib import Path

import pymupdf as fitz
import redis
from langchain_core.documents import Document
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from cache.redis_client import (
    get_cached_ocr_text,
    get_cached_vision_description,
    set_cached_ocr_text,
    set_cached_vision_description,
)
from ingestion.models import Asset, MultimodalChunk


_ocr_engine = None

VISION_PROMPT = """Describe this document image for retrieval by a study assistant.
Include visible headings, labels, values, relationships, and the main takeaway.
Transcribe legible text exactly when practical. Do not invent details.
Return one concise paragraph without markdown."""


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def _extract_ocr_text(asset: Asset) -> str:
    """Run RapidOCR directly on in-memory image bytes."""
    try:
        cached = get_cached_ocr_text(asset.data)
    except redis.RedisError:
        cached = None
    if cached:
        return cached

    import cv2
    import numpy as np

    image = cv2.imdecode(
        np.frombuffer(asset.data, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if image is None:
        raise ValueError(f"Could not decode image asset {asset.asset_id}")

    result, _ = _get_ocr_engine()(image)
    if not result:
        return ""

    lines = []
    for item in result:
        if len(item) >= 2 and item[1]:
            lines.append(str(item[1]).strip())
    text = "\n".join(line for line in lines if line)
    if text:
        try:
            set_cached_ocr_text(asset.data, text)
        except redis.RedisError:
            pass
    return text


def _vision_model() -> tuple[ChatNVIDIA, str]:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is required for visual extraction")
    model_name = os.getenv(
        "NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct"
    )
    return ChatNVIDIA(
        model=model_name,
        api_key=api_key,
    ), model_name


def _describe_asset(model: ChatNVIDIA, model_name: str, asset: Asset) -> str:
    try:
        cached = get_cached_vision_description(model_name, asset.data)
    except redis.RedisError:
        cached = None
    if cached:
        return cached

    encoded = base64.b64encode(asset.data).decode("ascii")
    response = model.invoke(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{asset.media_type};base64,{encoded}"
                        },
                    },
                ],
            }
        ]
    )
    description = getattr(response, "content", "")
    if not isinstance(description, str) or not description.strip():
        raise RuntimeError(f"NVIDIA vision model returned no description for {asset.asset_id}")
    description = description.strip()
    try:
        set_cached_vision_description(model_name, asset.data, description)
    except redis.RedisError:
        pass
    return description


def _image_asset(data: bytes, file_name: str, asset_id: str, page: int | None = None) -> Asset:
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(Path(file_name).suffix.lower())
    if media_type is None:
        raise ValueError(f"Unsupported image media type for '{file_name}'")
    return Asset(
        asset_id=asset_id,
        modality="image",
        media_type=media_type,
        data=data,
        page=page,
    )


def _extract_pdf_assets(file_path: str) -> list[Asset]:
    assets: list[Asset] = []
    with fitz.open(file_path) as pdf:
        for page_index, page in enumerate(pdf):
            page_number = page_index + 1
            images = page.get_images(full=True)
            if images:
                for image_index, image in enumerate(images):
                    xref = image[0]
                    image_data = pdf.extract_image(xref)
                    assets.append(
                        Asset(
                            asset_id=f"page-{page_number}-image-{image_index + 1}",
                            modality="image",
                            media_type=image_data["mime"],
                            data=image_data["image"],
                            page=page_number,
                        )
                    )
            elif not page.get_text("text").strip():
                # Render scanned pages in memory; no extracted file is written.
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                assets.append(
                    Asset(
                        asset_id=f"page-{page_number}-scan",
                        modality="image",
                        media_type="image/png",
                        data=pixmap.tobytes("png"),
                        page=page_number,
                    )
                )
    return assets


def extract_multimodal_chunks(
    file_path: str,
    original_file_name: str,
    documents: list[Document],
) -> list[MultimodalChunk]:
    """Extract text and visual units without persisting derived assets."""
    chunks = [
        MultimodalChunk(
            content=document.page_content,
            modality="text",
            metadata=dict(document.metadata),
        )
        for document in documents
        if document.page_content.strip()
    ]

    extension = Path(original_file_name).suffix.lower()
    if extension == ".pdf":
        assets = _extract_pdf_assets(file_path)
    elif extension in {".png", ".jpg", ".jpeg", ".webp"}:
        assets = [_image_asset(Path(file_path).read_bytes(), original_file_name, "image-1")]
    else:
        assets = []

    if assets:
        model = None
        model_name = None
        for asset in assets:
            ocr_text = _extract_ocr_text(asset)
            if ocr_text:
                metadata = {
                    "asset_id": asset.asset_id,
                    "modality": "text",
                    "extraction": "rapidocr",
                }
                if asset.page is not None:
                    metadata["page"] = asset.page
                chunks.append(
                    MultimodalChunk(
                        content=f"OCR text:\n{ocr_text}",
                        modality="text",
                        metadata=metadata,
                        asset=asset,
                    )
                )
            try:
                if model is None:
                    model, model_name = _vision_model()
                asset.caption = _describe_asset(model, model_name, asset)
            except Exception as error:
                print(f"[ingest] Vision description skipped for {asset.asset_id}: {error}")
                continue

            metadata = {"asset_id": asset.asset_id, "modality": asset.modality}
            if asset.page is not None:
                metadata["page"] = asset.page
            chunks.append(
                MultimodalChunk(
                    content=f"Visual content: {asset.caption}",
                    modality=asset.modality,
                    metadata=metadata,
                    asset=asset,
                )
            )
    return chunks


def load_asset(source_data: bytes, file_name: str, asset_id: str) -> Asset:
    """Reconstruct an indexed asset from the original source bytes."""
    if asset_id == "image-1":
        return _image_asset(source_data, file_name, asset_id)

    with fitz.open(stream=source_data, filetype="pdf") as pdf:
        if asset_id.endswith("-scan"):
            page_number = int(asset_id.split("-")[1])
            page = pdf[page_number - 1]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            return Asset(asset_id, "image", "image/png", pixmap.tobytes("png"), page_number)

        prefix, page_value, _, image_value = asset_id.split("-")
        page_number = int(page_value)
        image_number = int(image_value)
        page = pdf[page_number - 1]
        image = page.get_images(full=True)[image_number - 1]
        image_data = pdf.extract_image(image[0])
        return Asset(
            asset_id,
            "image",
            image_data["mime"],
            image_data["image"],
            page_number,
        )


def to_documents(
    chunks: list[MultimodalChunk],
    original_file_name: str,
    notebook_id: str,
    source_id: str,
) -> list[Document]:
    """Convert normalized chunks into the existing vector-store document shape."""
    documents = []
    for index, chunk in enumerate(chunks):
        metadata = {
            **chunk.metadata,
            "chunk_id": index,
            "source": original_file_name,
            "file_name": original_file_name,
            "notebook_id": notebook_id,
            "source_id": source_id,
            "modality": chunk.modality,
        }
        documents.append(Document(page_content=chunk.content, metadata=metadata))
    return documents
