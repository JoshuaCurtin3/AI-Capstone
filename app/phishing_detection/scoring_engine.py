"""The deterministic phishing risk-scoring engine.

This module (together with rules/) is the ONLY place allowed to produce the
numerical risk score. Requirements (see CLAUDE.md):

  - Deterministic: the same parsed email must always produce the same score.
    No randomness, no wall-clock/network dependence, no LLM calls.
  - Every individual rule in rules/ must be independently unit tested.
  - The Claude API (app.ai_analysis) may summarize *this* module's output in
    plain language, but must never feed back into or adjust the score.

TODO: implement calculate_risk_score by evaluating each rule in rules/ against
the parsed email and summing/combining their contributions.
"""

from __future__ import annotations


def calculate_risk_score(parsed_email: object) -> None:
    """Compute a deterministic phishing risk score for a parsed email."""
    raise NotImplementedError
