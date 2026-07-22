"""Typed structures returned by this app's parsing services.

These are the data contracts phishing_detection consumes — keep them stable
and independent of SQLAlchemy ORM models so the scoring engine can be tested
with plain data, without a database.

TODO: define e.g. a ParsedEmail dataclass (sender, headers, body, links,
attachments) once parsing logic is implemented.
"""
