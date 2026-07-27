"""Individual, independently testable phishing-detection rules.

Each module here exposes one or more pure `check_*(parsed_email) ->
list[Finding]` functions, grouped by category: spf.py, dkim.py, dmarc.py
(authentication), header_analysis.py, url_analysis.py,
attachment_analysis.py, content_analysis.py. `_auth_results.py` is a private
helper shared by the three authentication rules, not a rule itself. One
category = one file = one test module under tests/unit/. This keeps rules
easy to review, test, and reason about in isolation (see CLAUDE.md: "tests
for every analysis rule").
"""
