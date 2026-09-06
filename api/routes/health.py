from fastapi import APIRouter


router = APIRouter(tags=["Health"])


@router.get("/")
async def python_route():
    return {"message": "Hello from FastAPI!"}


@router.get("/health")
async def health():
    return {"status": "ok"}
