"""Shared Jinja2Templates instance used by every router.

Centralized so template globals (app_name, current_year) are set once and
every route - across every domain package - renders through the same
environment instead of each router instantiating its own.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import get_settings

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["app_name"] = get_settings().app_name
templates.env.globals["current_year"] = lambda: datetime.now(UTC).year
