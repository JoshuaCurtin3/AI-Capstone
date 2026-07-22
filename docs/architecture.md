# Architecture

## Layout philosophy

This repository combines two patterns:

1. **A shared horizontal layer** (`app/config`, `app/core`, `app/database`,
   `app/models`, `app/schemas`, `app/services`, `app/utils`) for code genuinely
   used by more than one domain.
2. **Vertical domain apps** (`app/auth`, `app/api`, `app/email_parser`,
   `app/phishing_detection`, `app/ai_analysis`), each a self-contained Django
   app owning its own `models.py`, `schemas.py`, `services.py`, and
   `migrations/`.

Domain-specific code lives in its domain app, not in the shared layer. The
shared layer only holds things with no single owning domain (e.g. an abstract
`TimeStampedModel` mixin, or the pipeline that orchestrates all three
analysis domains in order). This avoids two folders being responsible for the
same thing.

## The analysis pipeline

```
raw email
   -> app/email_parser      (parse into structured data)
   -> app/phishing_detection (deterministic risk score)
   -> app/ai_analysis        (Claude-generated explanation of that score)
   -> app/services/pipeline.py orchestrates the three calls above
   -> app/api                (exposes the result over HTTP)
```

**The score from `phishing_detection` is never altered after the fact.**
`ai_analysis` receives it as read-only input and may only produce explanatory
text. See CLAUDE.md for why this boundary is non-negotiable.

## Where future features go

| Adding...                                      | Goes in                                   |
|-------------------------------------------------|--------------------------------------------|
| A new scoring rule                              | `app/phishing_detection/rules/<rule>.py` + test in `tests/unit/` |
| A new field on the parsed-email data contract    | `app/email_parser/schemas.py` |
| A new persisted model for any domain             | that domain's own `models.py` |
| A new HTTP endpoint                              | `app/api/v1/` (routing) — calls into `app/services/pipeline.py` |
| A new AD/LDAP attribute needed at login          | `app/auth/backends.py` (and `app/auth/models.py` if it must be cached locally) |
| A cross-domain orchestration step                | `app/services/` |
| A mixin/base class used by 2+ domain apps        | `app/models/`, `app/schemas/`, or `app/core/` as appropriate |
| A generic helper with no domain ownership        | `app/utils/` |
| Nginx/Gunicorn/deploy changes                    | `docker/`, `.github/workflows/`, and this file |

## Deviations from a generic/FastAPI-style layout

- **No `alembic.ini`.** Django ships its own migration framework
  (`manage.py makemigrations` / `migrate`), tracked per-app under
  `<app>/migrations/`. Alembic is for SQLAlchemy-based projects; adding it
  here would create two competing migration systems for the same database.
- **`models/`, `schemas/`, `services/` are shared-only, not centralized.**
  Each domain app keeps its own `models.py`/`schemas.py`/`services.py`. This
  keeps Django's migration-per-app convention intact and avoids one giant
  `models/` package that every domain has to reach into.
- **`app.auth`'s Django app label is `capstone_auth`**, not `auth` — the
  default label collides with `django.contrib.auth`. See
  `app/auth/apps.py`.
