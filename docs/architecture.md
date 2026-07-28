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
| A new AD/LDAP attribute needed at login          | `app/auth/ldap_backend.py` + `app/auth/schemas.py`'s `AuthenticatedUser` (and `app/auth/models.py` if it must be cached locally, Phase 5+) |
| A new route requiring login                      | `Depends(app.auth.dependencies.require_user)` on the route - see `GET /account` in `app/auth/router.py` for a working example |
| A cross-domain orchestration step                | `app/services/` |
| A mixin/base class used by 2+ domain packages    | `app/models/`, `app/schemas/`, or `app/core/` as appropriate |
| A generic helper with no domain ownership        | `app/utils/` |
| Nginx/Uvicorn/Gunicorn/deploy changes            | `docker/`, `.github/workflows/`, and this file |

## Database and migrations (Phase 5)

- Models are SQLAlchemy 2.0 declarative classes (`Mapped`/`mapped_column`),
  living in each domain package's own `models.py`, built on the shared
  `Base` in `app/database/base.py`. `app/database/session.py` owns the
  engine/`sessionmaker`/`get_db()` FastAPI dependency.
- Schema changes are tracked as Alembic revisions under `alembic/versions/`,
  applied with `alembic upgrade head`. Every model change ships with its
  revision in the same PR — no implicit/auto-created schema drift.
  `alembic/env.py` reads the connection URL from `Settings.database_url`
  (i.e. `APP_DATABASE_URL`) rather than `alembic.ini`, since `alembic.ini`
  is committed and must never carry real credentials (CLAUDE.md's "no
  secrets in source control" rule); it only falls back to that default when
  a caller hasn't already set a URL, so
  `tests/integration/test_alembic_migrations.py` can point migrations at a
  separate `TEST_DATABASE_URL` via the Alembic Python API instead.
- `app/models/` holds only shared, reusable mixins (currently
  `TimeStampedMixin`: `created_at`/`updated_at`) — never a concrete,
  queryable table. Concrete tables belong to the domain package that owns
  them: `app/auth/models.py::User` and
  `app/phishing_detection/models.py::AnalysisResult`/`TriggeredRule`.
- **`User` never stores a credential.** Per CLAUDE.md's "no local password
  auth" rule, Active Directory over LDAPS remains the sole source of truth
  for identity/authorization on every login (see the Authentication section
  above) — `User` is a local cache (username, display_name, email) upserted
  by `app/auth/services.py::get_or_create_user` purely so
  `AnalysisResult.submitted_by` can reference *who* ran an analysis and
  `/dashboard` can filter by user.
- **`AnalysisResult.submitted_by_id` is nullable.** `/upload` is
  intentionally still public (Phase 6 decision), so an anonymous,
  unauthenticated visitor can submit an email for analysis; it's still
  recorded, just with no attributable user. `/dashboard` only shows the
  logged-in user's own results, so anonymous analyses never appear there
  (there's no identity to filter by).
- **Persistence is best-effort, never blocking.** Both the `/upload` save
  (`app/phishing_detection/services.py::save_analysis_result`) and the
  login-time `User` upsert (`app/auth/services.py::get_or_create_user`) are
  wrapped in try/except around `SQLAlchemyError` at their call sites
  (`app/api/v1/upload.py`, `app/auth/router.py`): a database outage is
  logged and swallowed, never turned into a 500 or a blocked login. This
  keeps `/upload` and `/login` working exactly as they did before Phase 5
  even if PostgreSQL is briefly unreachable — deliberate, since neither the
  deterministic risk score nor AD authentication should ever depend on
  database availability. `Settings.database_connect_timeout_seconds`
  (default 3s) bounds how long a failed connection attempt can take, so an
  unreachable database degrades to "briefly slower" rather than "hangs the
  request" - **must be an `int`, not a `float`: psycopg2's `connect_timeout`
  DSN parameter rejects a float value like `"3.0"` outright**, a real bug
  caught only by live-testing against an actually-unreachable database, not
  by the mocked/monkeypatched unit tests (which never touch the real
  connect path at all).
- **Integration tests require real PostgreSQL, never SQLite** (TASKS.md
  Phase 5's explicit requirement, since SQLite's type/constraint/cascade
  behavior differs meaningfully from Postgres). `tests/integration/test_database.py`,
  `test_dashboard.py`, and `test_alembic_migrations.py` all read
  `TEST_DATABASE_URL` and **skip themselves** (not fail) when it's unset or
  unreachable, so `pytest` stays green in environments with no Postgres
  available (this fully applies to the current CI workflow too, which has
  no Postgres service container until Phase 9) while still providing real
  coverage wherever a test database exists.

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

## Authentication (Phase 6)

- **LDAPS only, never local passwords.** `app/auth/ldap_backend.py::authenticate()`
  is the only place a login password is ever handled, and it's never compared
  locally - the real credential check is always a bind-as-user against Active
  Directory itself. `Settings.ldap_server_uri` is validated at startup to require
  the `ldaps://` scheme, and the backend also passes `use_ssl=True` explicitly to
  `ldap3.Server(...)` as a second, code-level guarantee.
- **Auth flow**: service-account bind (search-only) -> search for the user by
  `Settings.ldap_user_login_attribute` (the filter escapes the username via
  `ldap3.utils.conv.escape_filter_chars` to block LDAP filter injection) -> bind
  **as that user** with the submitted password -> only if that succeeds, resolve
  group authorization. Unknown username and wrong password both return `None`
  from `authenticate()` (no way to distinguish them - avoids user enumeration); a
  correct password but missing group membership is a separate case the router
  turns into a `403`, since identity was already proven.
- **Nested group membership is resolved client-side.** Active Directory's
  server-side nested-group matching rule (`LDAP_MATCHING_RULE_IN_CHAIN`, OID
  `1.2.840.113556.1.4.1941`) is not implemented by `ldap3`'s `MOCK_SYNC` test
  strategy - a filter using it silently returns zero results against the mock.
  Relying on it would ship an authorization-critical code path with no unit-test
  coverage, which cuts against CLAUDE.md's testing requirements. Instead,
  `_resolve_group_membership()` does a breadth-first walk outward from the
  user's direct `memberOf` list, reading each parent group's own `memberOf`
  attribute, bounded by `Settings.ldap_group_membership_max_depth` and a
  visited-DN set (cycle safety) - fully expressible with plain LDAP search/read
  operations, so it's fully covered by mocked tests.
- **Session cookie**: a custom signed cookie
  (`itsdangerous.URLSafeTimedSerializer`, keyed off the existing
  `Settings.secret_key` - no new secret) in `app/auth/session.py`, not
  Starlette's built-in `SessionMiddleware`, so the exact cookie flags are fully
  controlled: `HttpOnly` always, `Secure` gated on
  `Settings.environment == "production"` (mirrors the `docs_url` gating pattern
  below so local dev over plain HTTP still works), `SameSite=Lax`.
- **CSRF**: `app/core/security.py` implements a double-submit cookie (an
  unpredictable token set as a cookie and also embedded as a hidden form field;
  the two must match on submit). No server-side token store is needed, which
  matters since there's no session established yet when `/login` itself is
  submitted, and no database at all before Phase 5.
- **Request-scoped auth context**: `app/auth/middleware.py::AuthContextMiddleware`
  resolves `request.state.user` and `request.state.csrf_token` on every
  request (reading the session cookie, minting a CSRF cookie if one doesn't
  exist yet). This is auth-domain logic, so it lives under `app/auth/` per this
  file's "domain-specific code lives in its domain package" rule, not in the
  still-empty `app/core/middleware.py` stub. Templates read both directly off
  `request.state` (Jinja2Templates always injects `request`), so `base.html`'s
  navbar and the login/logout forms need nothing threaded through per-route.
- **Redirect-preserving-next**: `app/auth/dependencies.py::require_user` raises
  `app.auth.exceptions.AuthenticationRequiredError(next_path)` when there's no
  valid session; a handler registered in `app/main.py` turns that into a `303`
  redirect to `/login?next=<path>`. The `next` value is validated (must start
  with a single `/`, never `//`, never contain `://`) to block open-redirect
  abuse.
- **`/upload` is intentionally still public.** Phase 6 only ships the auth
  machinery itself; `GET /account` (gated by `Depends(require_user)`) is the
  real, working demonstration of route protection. Gating `/upload` is a
  decision left for whichever phase actually needs it.
- **Independent of scoring.** Nothing in `app/auth/` is imported by
  `app/phishing_detection/` or vice versa - the deterministic risk score stays
  a pure function of a parsed email, per CLAUDE.md's core rule, regardless of
  who is or isn't logged in.

## History: framework pivot

This project originally scaffolded as Django, then moved to FastAPI +
SQLAlchemy + Alembic (see TASKS.md Phase 1). Two points that fall out of that:

- **FastAPI has no built-in CSRF protection.** Django did; FastAPI doesn't.
  Any session-authenticated POST route needs an explicit CSRF mechanism added
  — see CLAUDE.md. Implemented in Phase 6 as `app/core/security.py`'s
  double-submit cookie, used by both `/login` and `/logout`.
- **`app.auth`'s Django app-label collision note no longer applies.** That
  was a Django-specific `INSTALLED_APPS` concern; FastAPI has no equivalent
  app registry, so there's nothing to rename here.
