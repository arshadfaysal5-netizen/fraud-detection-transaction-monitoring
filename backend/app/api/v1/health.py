from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["ops"], summary="Service health check")
async def health() -> dict:
    return {"status": "ok", "service": "fraud-backend"}


@router.get("/", tags=["ops"], include_in_schema=False)
async def root() -> dict:
    return {"service": "fraud-backend", "docs": "/docs", "health": "/health"}