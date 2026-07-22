"""Liveness/health check endpoint used by Docker and deployment automation."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return 200 with a static payload when the app process is up."""
    return {"status": "ok"}
