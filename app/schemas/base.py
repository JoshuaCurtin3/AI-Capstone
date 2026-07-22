"""Shared data-validation base types used across domain apps' schemas.py.

These are plain typed structures (e.g. dataclasses) used to pass validated
data between layers (email_parser -> phishing_detection -> ai_analysis)
without coupling them to Django's ORM models. Domain-specific schemas live in
each domain app's own schemas.py and may build on top of these.

TODO: add shared base dataclasses/enums here as concrete cross-domain needs
arise.
"""
