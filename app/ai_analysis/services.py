"""Generate a human-readable explanation for an already-computed risk score.

This function must treat the score and triggered rules as read-only input. It
must never return a value that overrides, adjusts, or substitutes for the
numerical score from app.phishing_detection.scoring_engine (see CLAUDE.md).

TODO: implement by prompting Claude (via client.py) with the score and
triggered rule identifiers, and returning plain-language explanation text.
"""

from __future__ import annotations


def generate_explanation(scoring_result: object) -> str:
    raise NotImplementedError
