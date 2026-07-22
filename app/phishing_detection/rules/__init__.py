"""Individual, independently testable phishing-detection rules.

Each rule should live in its own small module here (e.g. spf_dkim.py,
urgency_language.py, lookalike_domain.py) and expose a single pure function
that takes parsed-email data and returns its contribution to the score. One
rule = one file = one test module under tests/unit/. This keeps rules easy to
review, test, and reason about in isolation (see CLAUDE.md: "tests for every
analysis rule").
"""
