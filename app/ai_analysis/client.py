"""Thin wrapper around the Claude API client.

TODO: implement using the anthropic SDK, reading ANTHROPIC_API_KEY from
settings (sourced from the environment — see .env.example). Keep this module
limited to the raw API call; prompt construction and response handling belong
in services.py.
"""

from __future__ import annotations


def get_client() -> None:
    raise NotImplementedError
