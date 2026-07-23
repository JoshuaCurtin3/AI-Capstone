"""Safety guarantees for app.email_parser.parser that go beyond a single
rule: never dereference an extracted URL, never expose raw attachment
bytes on the returned model, and never crash on non-email garbage input.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from app.email_parser.parser import parse_email
from app.email_parser.schemas import AttachmentMeta

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parsing_never_opens_a_network_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """A phishing email is full of attacker-controlled URLs - parsing must
    never dereference any of them. Fail loudly if it tries to."""

    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("parse_email must never open a network connection")

    monkeypatch.setattr(socket.socket, "connect", _forbidden_connect)
    monkeypatch.setattr(socket, "create_connection", _forbidden_connect)

    parsed = parse_email(_load("phishing.eml"))

    assert len(parsed.urls) >= 1


def test_attachment_metadata_model_never_carries_raw_content() -> None:
    """Structural guarantee: AttachmentMeta has no field that could hold an
    attachment's raw bytes, so it's impossible to accidentally serialize or
    act on payload content downstream."""
    assert set(AttachmentMeta.model_fields) == {"filename", "content_type", "size_bytes", "sha256"}


def test_non_email_binary_garbage_does_not_raise() -> None:
    raw = bytes(range(256)) * 4

    parsed = parse_email(raw)

    assert parsed.attachments == []
    assert parsed.urls == []


def test_empty_input_does_not_raise() -> None:
    parsed = parse_email(b"")

    assert parsed.subject is None
    assert parsed.attachments == []
