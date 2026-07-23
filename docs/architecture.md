# Architecture

## Layout philosophy

This repository combines two patterns:

1. **A shared horizontal layer** (`app/core`, `app/database`, `app/models`,
   `app/schemas`, `app/services`, `app/utils`) for code genuinely used by more
   than one domain, plus `app/config.py` and `app/main.py` for app-level
   wiring.
2. **Vertical domain packages** (`app/auth`, `app/api`, `app/email_parser`,
   `app/phishing_detection`, `app/ai_analysis`), each owning its own
   `models.py` (SQLAlchemy), `schemas.py` (Pydantic), and `services.py`.

Domain-specific code lives in its domain package, not in the shared layer.
The shared layer only holds things with no single owning domain (e.g. a
`TimeStampedMixin`, or the pipeline that orchestrates all three analysis
domains in order). This avoids two folders being responsible for the same
thing.

## The analysis pipeline

```
raw email
   -> app/email_parser        (parse into structured data)          [Phase 3]
   -> app/phishing_detection  (deterministic risk score)             [Phase 4]
   -> app/ai_analysis         (Claude-generated explanation of that score) [Phase 7]
   -> app/services/pipeline.py orchestrates the three calls above
   -> app/api                 (exposes the result over HTTP)
```

**The score from `phishing_detection` is never altered after the fact.**
`ai_analysis` receives it as read-only input and may only produce explanatory
text. See CLAUDE.md for why this boundary is non-negotiable.

## Where future features go

| Adding...                                      | Goes in                                   |
|-------------------------------------------------|--------------------------------------------|
| A new scoring rule                              | `app/phishing_detection/rules/<rule>.py` + test in `tests/unit/` |
| A new field on the parsed-email data contract    | `app/email_parser/schemas.py` |
| A new persisted model for any domain             | that domain's own `models.py` (SQLAlchemy) + an Alembic revision |
| A new HTTP endpoint                              | `app/api/v1/` (routing) — calls into `app/services/pipeline.py` |
| A new AD/LDAP attribute needed at login          | `app/auth/ldap_backend.py` (and `app/auth/models.py` if it must be cached locally) |
| A cross-domain orchestration step                | `app/services/` |
| A mixin/base class used by 2+ domain packages    | `app/models/`, `app/schemas/`, or `app/core/` as appropriate |
| A generic helper with no domain ownership        | `app/utils/` |
| Nginx/Uvicorn/Gunicorn/deploy changes            | `docker/`, `.github/workflows/`, and this file |

## Database and migrations (Phase 5+)

- Models are SQLAlchemy declarative classes, living in each domain package's
  own `models.py`, built on the shared base in `app/database/base.py`.
- Schema changes are tracked as Alembic revisions under `alembic/versions/`,
  applied with `alembic upgrade head`. Every model change ships with its
  revision in the same PR — no implicit/auto-created schema drift.
- `app/models/` holds only shared, reusable mixins (e.g. a timestamp mixin) —
  never a concrete, queryable table. Concrete tables belong to the domain
  package that owns them, so it's obvious what a migration is "for."

## Configuration and templates (Phase 2)

- `app/config.py` defines a single `Settings` (pydantic-settings) class read
  from environment variables (`.env` locally, real env vars in CI/production)
  — see CLAUDE.md's "no secrets in source control" rule. `Settings.environment`
  ("development"/"production") gates dev-only conveniences — currently the
  interactive `/docs`/`/redoc` API docs — without a full settings-file
  hierarchy.
- `app/templates/` holds Jinja2 templates; `base.html` is the shared layout:
  a Bootstrap navbar, a `content` block, and a footer, plus Bootstrap CDN +
  `static/css/main.css`/`static/js/main.js` hooks. Page-specific templates
  extend it with `{% extends "base.html" %}` and override `title`/`content`
  (see `index.html`). `app_name` and `current_year` are registered as Jinja
  globals in `app/main.py` so every template can use them without repeating
  them in each route's context dict.
- `error.html` is the single template used for both HTTP errors (404, etc.)
  and unhandled exceptions — see the "Error handling" section below.
- `app/static/` is mounted at `/static` in `app/main.py` via FastAPI's
  `StaticFiles`.

## Error handling (Phase 2)

- `app/main.py` registers two handlers: one for `StarletteHTTPException`
  (renders `error.html` with the real status code/detail — e.g. a 404) and
  one for the base `Exception` (logs the real error server-side, then
  renders `error.html` with a generic message unless `Settings.debug` is
  true, in which case the real exception message is shown).
- **Do not pass `debug=` to the `FastAPI(...)` constructor.** Doing so makes
  Starlette's own debug-mode traceback page take over on any unhandled
  exception, bypassing the custom `Exception` handler entirely — which would
  leak full stack traces whenever debug is on, regardless of the handler's
  own logic. `app/main.py` always constructs `FastAPI(debug=False)` and lets
  the registered handler be the single place that decides what to show,
  driven by `Settings.debug` at request time.

## History: framework pivot

This project originally scaffolded as Django, then moved to FastAPI +
SQLAlchemy + Alembic (see TASKS.md Phase 1). Two points that fall out of that:

- **FastAPI has no built-in CSRF protection.** Django did; FastAPI doesn't.
  Any session-authenticated POST route (the Phase 6 login form, in
  particular) needs an explicit CSRF mechanism added — see CLAUDE.md.
- **`app.auth`'s Django app-label collision note no longer applies.** That
  was a Django-specific `INSTALLED_APPS` concern; FastAPI has no equivalent
  app registry, so there's nothing to rename here.
