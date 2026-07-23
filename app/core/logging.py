"""Logging configuration for the application.

Called once at process startup (see app/main.py). Verbosity is driven by
Settings.debug rather than hardcoded, per CLAUDE.md's environment-variable
configuration rule.
"""

from __future__ import annotations

import logging


def configure_logging(*, debug: bool) -> None:
    """Configure root logging handlers/format/level for the whole process."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
