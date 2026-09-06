# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Notebooks is a full-stack multimodal RAG platform. Users upload PDFs (or add websites/search results) and get:
- **Chat**: cited RAG-powered Q&A with streaming responses
- **Flashcards**: AI-generated active-recall cards
- **Mind maps**: hierarchical topic extraction
- **Podcasts**: bilingual TTS audio overviews via Sarvam AI

## Running the Stack

```bash
# Frontend (Next.js on :3000)
npm run dev

# Backend (FastAPI on :8001) — requires env vars from README.md
npm run backend

# Both at once (Windows PowerShell)
npm run dev:full
```

The Next.js dev server proxies `/api/python/*` → `http://127.0.0.1:8001` via `next.config.js` rewrites. In production (Vercel), routing is handled by `vercel.json`.

## Architecture

### Backend (`api/`) — Python FastAPI

The FastAPI app in `api/index.py` mounts routers from `api/routes/`. Route files follow the standard pattern: each owns a topic (`notebooks.py`, `sources.py`, `chat.py`, etc.).

Key modules:
- **`api/pipeline/`** — Core RAG logic. `ingest.py`/`ingest_worker.py` run PDF parsing → chunking → embedding → Qdrant upsert in background threads. `query.py` handles retrieval → NVIDIA rerank → prompt assembly → LLM streaming.
- **`api/vectorstore/`** — `qdrant_db.py` wraps the Qdrant collection (text chunks); `visual_qdrant.py` handles image-asset retrieval (disabled by `ENABLE_VISUAL_RETRIEVAL=false`).
- **`api/db/`** — `base.py` is the top-level `Database` facade. Sub-modules (`notebooks.py`, `sources.py`, `messages.py`, `flashcards.py`, `podcasts.py`, `mindmaps.py`) implement collection-level CRUD. `mongo_client.py` bootstraps MongoDB with auto-indexes; `gridfs_client.py` handles file storage.
- **`api/routes/dependencies.py`** — Provides the `get_db()` singleton used by all route handlers. This is where DB instance management lives.
- **`api/ingestion/`** — `extractor.py` uses `pymupdf4llm` + `rapidocr` for PDF text and visual-asset extraction; `splitter.py` chunks text via LangChain; `embedder.py` wraps the NVIDIA embedding model.
- **`api/llm/chat_model.py`** — Azure OpenAI chat wrapper.
- **`api/audio/`** — Podcast script generation (`script_gen.py`) + Sarvam AI TTS chunking (`audio_gen.py`).
- **`api/mindmap/mindmapgen.py`** — LLM-driven mind map JSON generation.
- **`api/web/`** — Firecrawl-based web scraping for website sources.
- **`api/cache/redis_client.py`** — Redis client for RAG response caching and cache invalidation.

### Frontend (`app/`) — Next.js 16 (App Router, React 19)

- **`app/notebooks/[id]/page.tsx`** — The main workspace. All modal views (chat, sources, flashcards) live here.
- **`lib/api.ts`** — API client. All calls go through `/api/python/*` which rewrites to the FastAPI backend.

### Dependency Graph

```
User upload → FastAPI /sources POST
  → GridFS storage (pdf_bucket)
  → background thread: ingest_worker.process_file_source()
    → extractor.py (pymupdf4llm + rapidocr) → text + assets
    → splitter.py → chunks
    → embedder.py → Qdrant upsert (text + visual)

User chat → FastAPI /chat POST
  → Redis cache check
  → embedder → Qdrant dense retrieval (k=12) + visual retrieval
  → reranker (NVIDIA) → top 5
  → chat_model (Azure OpenAI) → SSE stream
  → MongoDB message history save + Redis cache write
```

## Environment Variables

Essential vars (see `api/.env.example` and root `.env.example`):
- `MONGODB_URI`, `MONGODB_DB` — MongoDB Atlas or local
- `REDIS_URL` — Redis connection
- `QDRANT_URL`, `QDRANT_API_KEY` — Vector DB
- `AZURE_OPENAI_*` — Chat + embeddings
- `NVIDIA_API_KEY` — Reranker + visual captions
- `SARVAM_API_KEY` — Text-to-speech
- `ENABLE_VISUAL_RETRIEVAL` — Toggle image-vector search (default `true`)

## Key Patterns

- **Background ingestion**: Source upload is async. `sources.py` spawns a `threading.Thread` that calls `process_file_source()` / `process_web_source()`. Status transitions: `indexing` → `ready` / `failed`.
- **SSE streaming**: Chat uses Server-Sent Events (`StreamingResponse` with `media_type="text/event-stream"`). Client in `lib/api.ts` parses `data: {type: "chunk"|"citations"|"error"}`.
- **Hard delete cascade**: `delete_source` in `sources.py` removes from Qdrant, GridFS, and MongoDB in sequence. `delete_notebook_rows` in `base.py` cascades to all child collections.
- **Visual retrieval**: Controlled by `ENABLE_VISUAL_RETRIEVAL`. Uses `visual_qdrant.py` for image vector search with an `OPENROUTER_EMBEDDING_TIMEOUT` bound (default 10s).
- **Cache invalidation**: `invalidate_notebook_cache()` in `redis_client.py` is called after source add/delete. RAG responses are cached with a 1h TTL.
