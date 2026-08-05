from datetime import datetime

from fastapi import APIRouter

router = APIRouter()

START_TIME = datetime.utcnow()


@router.get("/health")
async def health():
    uptime = (datetime.utcnow() - START_TIME).total_seconds()
    return {"status": "ok", "uptime": uptime}


@router.get("/ready")
async def ready():
    # Placeholder for readiness checks
    return {"ready": True}
