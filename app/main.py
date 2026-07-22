"""FastAPI application entry point.

Keep this file thin: it wires together settings, static files, templates, and
routers. Route handlers and business logic belong in their owning module.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.health import router as health_router
from app.config import get_settings

BASE_DIR = Path(__file__).resolve().parent

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(health_router)


@app.get("/")
def index(request: Request) -> object:
    """Render the base layout to confirm the Jinja2 + Bootstrap setup works."""
    return templates.TemplateResponse(request, "base.html", {"app_name": settings.app_name})
