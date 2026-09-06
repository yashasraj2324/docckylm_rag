from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline.naming import generate_notebook_title
from routes.dependencies import get_db
from vectorstore import qdrant_db
from vectorstore.visual_qdrant import delete_by_notebook as delete_visual_by_notebook


router = APIRouter(tags=["Notebooks"])


class NotebookCreate(BaseModel):
    """Request body for creating a notebook."""

    title: str | None = "Untitled notebook"


@router.get("/notebooks")
async def list_notebooks():
    """Return all notebooks for the demo user, ordered by most-recently updated."""
    return get_db().list_notebooks()


@router.post("/notebooks", status_code=201)
async def create_notebook(request: NotebookCreate = NotebookCreate()):
    """Create a new notebook."""
    title = (request.title or "Untitled notebook").strip()
    notebook = get_db().create_notebook(title=title)
    return JSONResponse(content=notebook, status_code=201)


@router.delete("/notebooks/{notebook_id}")
async def delete_notebook(notebook_id: str):
    """Hard delete a notebook from MongoDB (DB + GridFS) and Qdrant."""
    db = get_db()

    try:
        qdrant_db.delete_by_notebook(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to delete from Qdrant: {e}")
    try:
        delete_visual_by_notebook(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to delete visual vectors from Qdrant: {e}")

    try:
        db.delete_storage_prefix(notebook_id)
    except Exception as e:
        print(f"Warning: Failed to delete from GridFS: {e}")

    db.delete_notebook_rows(notebook_id)

    return {"success": True}


@router.post("/notebooks/{notebook_id}/auto-name")
async def auto_name_notebook(notebook_id: str):
    """Generate a dynamic title for the notebook based on its uploaded content."""
    try:
        title = generate_notebook_title(notebook_id)
        get_db().rename_notebook(notebook_id, title)
        return {"title": title}
    except Exception as e:
        print(f"Error auto-naming notebook {notebook_id}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
