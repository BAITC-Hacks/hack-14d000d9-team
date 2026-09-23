"""Phase 1 composition root. Every application lifespan owns its HTTP client."""
import logging
import secrets
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, products
from app.clients.ekt_client import EKTClient, MockEKTClient, ProductDetailClient
from app.config import Settings
from app.dependencies import Services
from app.exceptions import BridgeError, ErrorContent, ErrorEnvelope
from app.services.product_service import ProductService

logger = logging.getLogger("ekt_bridge.api")


def error_response(request: Request, error: BridgeError) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorContent(code=error.code, message=error.message, details=error.details),
        request_id=getattr(request.state, "request_id", "unassigned"),
    )
    return JSONResponse(status_code=error.status, content=envelope.model_dump(mode="json"))


def create_app(
    settings: Settings | None = None, *,
    upstream_client: ProductDetailClient | None = None,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()
    if upstream_client is not None and upstream_client.mode != config.ekt_mode:
        raise ValueError("Injected client source mode must match EKT_MODE.")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            timeout=config.ekt_timeout_seconds, follow_redirects=False, trust_env=False,
            transport=http_transport,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        ) as http:
            client = upstream_client
            if client is None:
                client = MockEKTClient() if config.ekt_mode == "mock" else EKTClient(http, config)
            application.state.http_client = http
            application.state.services = Services(config, client, ProductService(client))
            yield

    application = FastAPI(
        title="EKT Bridge — Phase 1", version="0.1.0",
        description=(
            "Read-only health and product details. X-EKT-Source identifies mock or live evidence. "
            "Money is serialized as decimal strings; unknown values remain null. "
            "No cart, sessions, confirmation, search, analogs, or advanced stock logic."
        ),
        lifespan=lifespan,
        responses={status: {"model": ErrorEnvelope} for status in (404, 422, 500, 502, 503)},
    )

    @application.exception_handler(BridgeError)
    async def bridge_error_handler(request: Request, exc: BridgeError) -> JSONResponse:
        return error_response(request, exc)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        invalid_id = any("product_id" in error["loc"] for error in exc.errors())
        return error_response(request, BridgeError(
            "INVALID_PRODUCT_ID" if invalid_id else "VALIDATION_ERROR",
            "Product ID must be a positive integer." if invalid_id else "Request input is invalid.",
            422,
        ))

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        response = error_response(request, BridgeError(
            "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
            "The requested route was not found." if exc.status_code == 404 else "The HTTP request is not supported.",
            exc.status_code,
        ))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = secrets.token_hex(16)
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Keep a diagnostic, but omit exception text, locals, URL, and payload.
            frames = ",".join(f"{frame.name}:{frame.lineno}" for frame in traceback.extract_tb(exc.__traceback__))
            logger.error(
                "request_id=%s error_type=%s frames=%s",
                request.state.request_id, type(exc).__name__, frames,
            )
            response = error_response(request, BridgeError("INTERNAL_ERROR", "An internal error occurred.", 500))
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-EKT-Source"] = config.ekt_mode
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.info(
            "request_id=%s operation=%s status=%s duration_ms=%.2f",
            request.state.request_id, getattr(route, "name", "unmatched"),
            response.status_code, (perf_counter() - started) * 1000,
        )
        return response

    application.include_router(health.router)
    application.include_router(products.router)
    return application


app = create_app()
