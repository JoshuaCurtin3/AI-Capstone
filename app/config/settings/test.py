"""Settings used by the automated test suite (pytest-django, CI)."""

from .base import *  # noqa: F403

DEBUG = False

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # fast hashing for tests only
]
