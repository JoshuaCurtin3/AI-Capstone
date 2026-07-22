"""Abstract model mixins shared by multiple domain apps.

Domain-specific models (e.g. app/email_parser/models.py) should inherit from
these where relevant instead of redefining the same fields. This module must
only contain abstract=True models — concrete, queryable models belong in
their owning domain app so migrations stay colocated with the app that owns
the table.
"""

from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """Adds created_at / updated_at timestamps to a model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
