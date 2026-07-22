"""Cross-domain orchestration: the end-to-end email analysis pipeline.

This is the only place allowed to call across all three analysis domains in
sequence. It must not contain parsing, scoring, or explanation logic itself —
that stays in email_parser/phishing_detection/ai_analysis respectively. This
module only coordinates the order of calls and passes data between them.
"""

from __future__ import annotations


def analyze_email(raw_email: bytes) -> None:
    """Run the full pipeline: parse -> score -> explain.

    TODO: implement once email_parser, phishing_detection, and ai_analysis
    each expose their real service functions. The score returned by
    phishing_detection must be passed to ai_analysis unchanged — ai_analysis
    may only add an explanation, never alter the score (see CLAUDE.md).
    """
    raise NotImplementedError
