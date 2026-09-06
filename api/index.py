"""
FastAPI application for AI Notebooks.

Endpoint implementations live in :mod:`routes` and are registered here so
the application setup remains separate from the API surface.
"""

import os
import sys

from bson import ObjectId
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telemetry import init_telemetry

# Initialize Logfire telemetry (Pydantic, PyMongo, Redis, LangChain, OpenAI)
init_telemetry()

from db import Database
from routes.assets import router as assets_router
from routes.chat import router as chat_router
from routes.generated import router as generated_router
from routes.health import router as health_router
from routes.notebooks import NotebookCreate, router as notebooks_router
from routes.sources import router as sources_router


Database().list_notebooks()
print("Connected to MongoDB successfully")

app = FastAPI(title="AI Notebooks API")
init_telemetry(app)



@app.middleware("http")
async def validate_notebook_path(request: Request, call_next):
    path_parts = request.url.path.strip("/").split("/")
    if len(path_parts) >= 2 and path_parts[0] == "notebooks":
        notebook_id = path_parts[1]
        if not ObjectId.is_valid(notebook_id):
            return JSONResponse(
                content={"error": "Invalid notebook ID"},
                status_code=400,
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(notebooks_router)
app.include_router(sources_router)
app.include_router(chat_router)
app.include_router(assets_router)
app.include_router(generated_router)

__all__ = ["NotebookCreate", "app"]
