import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

logger = logging.getLogger("financial_leakage")


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    component = "request"
    for segment, category in (
        ("/health/ready", "readiness"),
        ("/proof/", "proof"),
        ("/recovery/", "recovery"),
        ("/financial/", "financial"),
        ("/source-", "source"),
    ):
        if segment in request.url.path:
            component = category
            break
    logger.warning(
        "operation_failed",
        extra={"component": component, "reason_code": code, "status_code": status},
    )
    request_id = getattr(request.state, "request_id", None)
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, request_id=request_id))
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        code = f"http_{exc.status_code}"
        if isinstance(exc.detail, dict):
            if isinstance(exc.detail.get("code"), str) and isinstance(
                exc.detail.get("message"), str
            ):
                code, message = exc.detail["code"], exc.detail["message"]
        response = error_response(request, exc.status_code, code, message)
        response.headers.update(exc.headers or {})
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo request bodies or financial document contents.
        return error_response(request, 422, "validation_error", "Request validation failed")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_error",
            extra={
                "exception_type": type(exc).__name__,
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        return error_response(request, 500, "internal_error", "An unexpected error occurred")
