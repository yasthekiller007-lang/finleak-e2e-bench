import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.documents import UploadBodyLimit
from app.api.documents import router as documents_router
from app.api.financial import router as financial_router
from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.me import router as me_router
from app.api.proof import ProofBodyGuard
from app.api.proof import router as proof_router
from app.api.recovery import router as recovery_router
from app.api.saved_views import router as saved_views_router
from app.api.source_gate import router as source_gate_router
from app.auth.oidc import TokenVerifier, build_token_verifier
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.http_boundary import HttpBoundary
from app.core.logging import configure_logging, request_id_context
from app.core.preflight import (
    ReadinessFailure,
    production_configuration,
    readiness,
    scanner_database_readiness,
)
from app.db.session import create_database_engine
from app.modules.scanner import build_scanner
from app.modules.source_preservation import PreservedObjectStorage
from app.modules.storage import build_storage
from app.operations.intake import IntakeCoordinator, IntakeError
from app.operations.source_gate import ReleasedObjectStorage, SourceGateError
from app.saved_views.boundary import SavedViewBodyGuard

logger = logging.getLogger("financial_leakage")


def create_app(
    settings: Settings | None = None, *, token_verifier: TokenVerifier | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    if token_verifier is not None and settings.environment != "test":
        raise ValueError("Injected identity verifiers are allowed only in test applications")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            production_configuration(settings)
        except ReadinessFailure as exc:
            logger.error(
                "readiness_failed", extra={"component": "readiness", "reason_code": exc.code}
            )
            raise
        # The lifespan owns only engines it created. Test/embedded callers may
        # replace state binds with an externally owned Engine or Connection.
        database_engine = create_database_engine(settings)
        scanner_engine = None
        try:
            app.state.database_engine = database_engine
            app.state.intake = IntakeCoordinator(database_engine)
            app.state.token_verifier = token_verifier or build_token_verifier(settings)
            app.state.settings = settings
            scanner_engine = create_database_engine(
                settings.model_copy(
                    update={
                        "database_url": settings.scanner_database_url,
                        "database_pool_size": 1,
                        "database_max_overflow": 0,
                    }
                )
            )
            app.state.scanner_engine = scanner_engine
            app.state.scanner = build_scanner(settings)
            app.state.raw_storage = build_storage(settings)
            app.state.preserved_storage = PreservedObjectStorage(
                app.state.raw_storage, database_engine
            )
            app.state.storage = ReleasedObjectStorage(app.state.preserved_storage, database_engine)
            if settings.environment == "production":
                scanner_database_readiness(scanner_engine, settings)
                readiness(
                    database_engine,
                    settings,
                    storage_probe=getattr(app.state.storage, "healthcheck", None),
                    scanner_probe=app.state.scanner.healthcheck,
                )
            yield
        except ReadinessFailure as exc:
            logger.error(
                "readiness_failed", extra={"component": "readiness", "reason_code": exc.code}
            )
            raise
        finally:
            try:
                if scanner_engine is not None:
                    scanner_engine.dispose()
            finally:
                if database_engine is not None:
                    database_engine.dispose()

    app = FastAPI(
        title="Financial Leakage AI",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    app.add_middleware(HttpBoundary)
    app.add_middleware(SavedViewBodyGuard)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts, www_redirect=False
    )
    app.add_middleware(UploadBodyLimit, max_bytes=settings.max_upload_bytes + 1024 * 1024)
    app.add_middleware(ProofBodyGuard, max_bytes=settings.proof_limits.request_bytes)
    from app.api.recovery import RecoveryBodyGuard

    app.add_middleware(RecoveryBodyGuard, max_bytes=settings.recovery_limits.request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
        expose_headers=[
            "X-Request-ID",
            "Idempotency-Key",
            "Retry-After",
            "X-Artifact-SHA256",
            "X-Source-SHA256",
        ],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        try:
            request_id = str(UUID(request.headers.get("X-Request-ID", "")))
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            for name, value in {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": (
                    "frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
                ),
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            }.items():
                response.headers.setdefault(name, value)
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "<unmatched>"),
                    "status_code": response.status_code,
                },
            )
            return response
        finally:
            request_id_context.reset(token)

    register_error_handlers(app)

    from sqlalchemy.exc import DBAPIError

    from app.core.errors import error_response
    from app.proof.budget import ProofError

    @app.exception_handler(DBAPIError)
    async def database_error(request: Request, exc: DBAPIError):
        if "/proof/" in request.url.path:
            logger.warning("proof_transaction_retry")
            return error_response(
                request,
                503,
                "proof_transaction_retry",
                "Proof transaction could not complete safely; retry later",
            )
        logger.error("unhandled_error", extra={"exception_type": type(exc).__name__})
        return error_response(request, 500, "internal_error", "An unexpected error occurred")

    from app.modules.s3_storage import StorageFailure

    @app.exception_handler(StorageFailure)
    async def storage_failure(request: Request, exc: StorageFailure):
        logger.warning("source_store_failure", extra={"reason_code": exc.code})
        response = error_response(request, 503, exc.code, "Private source storage is unavailable")
        response.headers["Retry-After"] = "5"
        return response

    @app.exception_handler(IntakeError)
    async def intake_failure(request: Request, exc: IntakeError):
        response = error_response(
            request,
            exc.status,
            exc.code,
            "Document operation could not be admitted safely; retry later",
        )
        response.headers["Retry-After"] = "60" if exc.status == 429 else "5"
        return response

    @app.exception_handler(SourceGateError)
    async def source_gate_failure(request: Request, exc: SourceGateError):
        response = error_response(
            request, exc.status, exc.code, "Source availability action could not complete safely"
        )
        if exc.status == 503:
            response.headers["Retry-After"] = "5"
        return response

    @app.exception_handler(ProofError)
    async def proof_error(request: Request, exc: ProofError):
        response = error_response(request, exc.status, exc.code, exc.message)
        if exc.status == 429:
            response.headers["Retry-After"] = "60"
        return response

    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(documents_router)
    app.include_router(intelligence_router)
    app.include_router(source_gate_router)
    app.include_router(financial_router)
    app.include_router(saved_views_router)
    app.include_router(proof_router)
    app.include_router(recovery_router)
    return app


app = create_app()
