"""Application-wide exception types shared across domain apps.

Domain-specific exceptions should subclass these rather than raising bare
Exception, so callers can catch failures at the right level of granularity.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application-raised (non-framework) errors."""


class ConfigurationError(AppError):
    """Raised when required configuration/environment variables are missing."""
