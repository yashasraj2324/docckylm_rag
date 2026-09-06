from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from ingestion.extractor import load_asset
from routes.dependencies import get_db


router = APIRouter(tags=["Assets"])


@router.get("/notebooks/{notebook_id}/assets/{source_id}/{asset_id}")
async def get_asset(notebook_id: str, source_id: str, asset_id: str):
    db = get_db()
    source = next(
        (item for item in db.list_sources(notebook_id) if item["id"] == source_id),
        None,
    )
    if not source or source.get("gridfs_file_id") in (None, "web", "search"):
        return JSONResponse(content={"error": "Asset not found"}, status_code=404)
    try:
        asset = load_asset(
            db.download_source_file(source["gridfs_file_id"]),
            source["file_name"],
            asset_id,
        )
    except Exception as error:
        print(f"[assets] Asset not found for {asset_id}: {error}")
        return JSONResponse(content={"error": "Asset not found"}, status_code=404)
    return Response(content=asset.data, media_type=asset.media_type)
