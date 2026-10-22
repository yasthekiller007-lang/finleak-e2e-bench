import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.errors import ErrorResponse
from app.core.preflight import ReadinessFailure, scanner_database_readiness
from app.core.preflight import readiness as check_readiness

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
def readiness(request: Request) -> HealthResponse:
    engine = request.app.state.database_engine
    if engine is None:
        raise HTTPException(503, "Database is not configured")
    try:
        if request.app.state.settings.environment == "production":
            scanner_database_readiness(request.app.state.scanner_engine, request.app.state.settings)
        check_readiness(
            engine,
            request.app.state.settings,
            storage_probe=getattr(request.app.state.storage, "healthcheck", None),
            scanner_probe=getattr(getattr(request.app.state, "scanner", None), "healthcheck", None),
        )
    except ReadinessFailure as exc:
        logging.getLogger("financial_leakage").error(
            "readiness_failed", extra={"component": "readiness", "reason_code": exc.code}
        )
        raise HTTPException(503, {"code": exc.code, "message": "Application is not ready"}) from exc
    return HealthResponse(status="ready")
