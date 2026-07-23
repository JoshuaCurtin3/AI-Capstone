"""FastAPI application entry point.

Keep this file thin: it wires together settings, logging, static files,
templates, routers, and error handlers. Route handlers and business logic
belong in their owning module.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.v1.upload import router as upload_router
from app.config import get_settings
from app.core.logging import configure_logging
from app.core.templates import templates

BASE_DIR = Path(__file__).resolve().parent

settings = get_settings()
configure_logging(debug=settings.debug)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    # Deliberately not passing debug=settings.debug here: FastAPI/Starlette's
    # own debug mode renders a raw traceback HTML page and bypasses the
    # unhandled_exception_handler below entirely. Our handler is the single
    # place that decides (via settings.debug) whether to include exception
    # details, so app-level debug must stay off.
    debug=False,
    # Interactive API docs are a development convenience, not something to
    # expose by default in production (CLAUDE.md's "secure defaults" rule).
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(health_router)
app.include_router(upload_router)


@app.get("/")
def index(request: Request) -> Response:
    """Render the home page."""
    return templates.TemplateResponse(request, "index.html")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Render HTTP errors (404, 403, ...) as a Bootstrap-styled page."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": exc.status_code, "message": exc.detail},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Catch-all for unhandled errors: log the real exception, never leak
    internals to the client outside of debug mode.
    """
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    message = str(exc) if settings.debug else "An unexpected error occurred."
    return templates.TemplateResponse(
        request, "error.html", {"status_code": 500, "message": message}, status_code=500
    )
