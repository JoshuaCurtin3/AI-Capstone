# AI-Capstone — Phishing Email Analyzer

A FastAPI web application that analyzes submitted emails and produces a phishing risk
score. The risk score is always computed by a deterministic, rule-based scoring engine;
the Claude API is used only to turn an already-computed score into a human-readable
explanation. See [CLAUDE.md](CLAUDE.md) for the full set of project rules,
[TASKS.md](TASKS.md) for the phased project roadmap, and
[docs/architecture.md](docs/architecture.md) for the detailed structure of this repo.

## Stack

- **Backend**: FastAPI (ASGI)
- **Templates / UI**: Jinja2 + Bootstrap
- **Database**: PostgreSQL via SQLAlchemy, migrations via Alembic
- **App server**: Uvicorn (behind Gunicorn in production), reverse-proxied by Nginx
- **Auth**: Windows Server 2025 Active Directory over LDAPS
- **AI**: Claude API (explanation generation only, never scoring)
- **CI/CD**: GitHub Actions
- **Host**: Ubuntu Server

## Repository layout

```
app/                    FastAPI application package (source root)
  main.py               FastAPI app instance, router/static/template wiring
  config.py             Typed settings (pydantic-settings), read from environment
  core/                 Cross-cutting concerns: exceptions, middleware, logging
  database/             DB-level helpers not tied to a specific domain
  models/                Shared SQLAlchemy model mixins used across domain packages
  schemas/               Shared data-validation base classes/types
  services/              Cross-domain orchestration (e.g. the end-to-end analysis pipeline)
  auth/                  LDAPS/Active Directory authentication (Phase 6)
  api/                   HTTP routing layer (thin, delegates to services)
  email_parser/          Parses raw email input into structured data (Phase 3)
  phishing_detection/    The deterministic risk-scoring engine (Phase 4)
  ai_analysis/           Claude API explanation generation (Phase 7)
  templates/             Shared Jinja2 templates
  static/                Shared static assets (css/js/images)
  utils/                 Small generic, domain-agnostic helpers
tests/                  unit/, integration/, fixtures/ (mirrors app/ by domain)
docs/                   Architecture, deployment, and scoring-rule documentation
scripts/                Local dev and deployment helper scripts
docker/                 Nginx and app-server configuration used by the containers
.github/workflows/      CI (lint/test) and deploy pipelines
```

See [docs/architecture.md](docs/architecture.md) for the reasoning behind this layout
and where each future feature should live.

## Local development setup

```bash
cp .env.example .env        # fill in real values, never commit this file
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

`APP_ENVIRONMENT=development` (the default) enables the interactive API docs at
`/docs`/`/redoc`; set it to anything else (e.g. `production`) to disable them.

## Application foundation (Phase 2)

- **Pages**: `/` (home) and `/health` (JSON health check), sharing a common
  `app/templates/base.html` layout with a Bootstrap navbar and footer.
- **Error handling**: unknown routes and other HTTP errors, plus any unhandled
  exception, render the same Bootstrap-styled error page. Exception details are only
  included in the response when `APP_DEBUG=true` — otherwise a generic message is
  shown and the real exception is logged server-side.
- **Configuration**: `app/config.py` defines a single `Settings` object
  (`APP_SECRET_KEY`, `APP_DEBUG`, `APP_ENVIRONMENT`, `APP_NAME`) read from the
  environment — see `.env.example`.

## Email parsing (Phase 3)

- **Page**: `/upload` — paste a raw email or upload an `.eml` file (max size set by
  `APP_MAX_EMAIL_UPLOAD_BYTES`, default 10 MB).
- **Parsing**: `app/email_parser/parser.py` extracts headers (Subject, From, To, Date,
  Reply-To, Return-Path, Message-ID, every Authentication-Results/Received header),
  plain-text and HTML bodies, URLs (flagging obfuscated display-text-vs-href
  mismatches), and attachment metadata (filename, content-type, size, SHA-256) using
  only the Python standard library — no new dependencies.
- **Safety**: attachment payloads are only ever hashed/sized in memory, never written
  to disk or executed; extracted URLs are never fetched/visited; malformed input is
  handled without crashing (see `tests/unit/test_email_parser_safety.py`).

## Phishing risk scoring (Phase 4)

- **Page**: `/upload` results now also show a deterministic risk score and its
  triggered findings immediately below the parsed email.
- **Scoring**: `app/phishing_detection/scoring_engine.py::calculate_risk_score` runs
  every rule in `app/phishing_detection/rules/` against the parsed email, sums their
  point contributions, and clamps the total to **0-100**: **0-24 Low, 25-49 Medium,
  50-74 High, 75-100 Critical**. It is a pure function of the parsed email — no network
  calls, no randomness, and no AI/LLM involvement (see CLAUDE.md's core rule).
- **Rule categories**: authentication (SPF/DKIM/DMARC failure, missing
  Authentication-Results header — read from the header the receiving mail server
  already added, not re-verified live via DNS, to keep scoring deterministic), header
  analysis (Reply-To/Return-Path mismatch, suspicious display name, excessive Received
  headers), URL analysis (IP-literal hosts, punycode, shorteners, suspicious TLDs,
  insecure HTTP, display-text/destination mismatch), attachment analysis (executable
  and double extensions, macro-enabled Office files, password-protected/general
  archives), and content analysis (urgency language, credential harvesting, payment/
  invoice scams, password-reset scams, brand impersonation). Every rule is documented
  in [docs/scoring_rules.md](docs/scoring_rules.md) with its point value and rationale.
- **Not yet implemented**: AI-generated explanations of a finding are Phase 7's job —
  each `Finding.explanation` here is a fixed, rule-authored sentence, not LLM output.

## Database and analysis history (Phase 5)

- **Page**: `/dashboard` (login-required) — shows the logged-in user's own analysis
  history, newest first: date, subject, from address, score, classification, and
  finding count.
- **Persistence**: every `/upload` submission is saved as an `AnalysisResult` row (one
  `TriggeredRule` row per finding) via `app/phishing_detection/services.py::save_analysis_result`,
  right after `calculate_risk_score` runs — the score itself is computed exactly as in
  Phase 4; this module only ever *stores* an already-computed result, never adjusts one.
  `AnalysisResult.submitted_by_id` is nullable, since `/upload` is intentionally still
  public (Phase 6 decision) and an anonymous visitor's analysis is still recorded, just
  unattributed.
- **User records**: `app/auth/models.py::User` is a local cache (username, display
  name, email) upserted at login time — it **never stores a password or any AD
  credential**; Active Directory over LDAPS remains the sole source of truth for
  identity/authorization on every login (Phase 6 is untouched by this).
- **Best-effort, never blocking**: both the `/upload` save and the login-time `User`
  upsert are wrapped in try/except around database errors and simply logged on
  failure — a PostgreSQL outage degrades to "this analysis wasn't saved," never a 500
  or a blocked login. `APP_DATABASE_CONNECT_TIMEOUT_SECONDS` (default 3s) bounds how
  long a failed connection attempt can take.
- **Migrations**: SQLAlchemy 2.0 models + Alembic, `alembic upgrade head` /
  `alembic downgrade base` (see `alembic/versions/0001_initial.py`). `alembic/env.py`
  reads the connection string from `APP_DATABASE_URL`, never from the committed
  `alembic.ini`, per CLAUDE.md's "no secrets in source control" rule.
- **Config**: `APP_DATABASE_URL` (must be `postgresql://` or `postgresql+<driver>://`)
  and `APP_DATABASE_CONNECT_TIMEOUT_SECONDS` in `.env.example`.
- **Testing**: `tests/integration/test_database.py`, `test_dashboard.py`, and
  `test_alembic_migrations.py` run against a **real** PostgreSQL database (never
  SQLite, to match production) via `TEST_DATABASE_URL` — they skip themselves (not
  fail) when it's unset or unreachable, so `pytest` stays green without a database
  available. Point `TEST_DATABASE_URL` at a disposable database to exercise them for
  real; see `docs/architecture.md`'s Database section for details.

## Active Directory authentication (Phase 6)

- **Pages**: `/login` (GET renders the form, POST authenticates), `/logout`
  (POST), `/account` — a minimal protected page (`Depends(require_user)`)
  showing the logged-in user's info; demonstrates route protection end-to-end.
  `/upload` is intentionally still public in this phase.
- **LDAPS only, zero local passwords**: `app/auth/ldap_backend.py::authenticate()`
  binds against Windows Server 2025 AD over LDAPS — a service account searches
  for the user, then a second bind *as that user* with the submitted password
  is the actual credential check. `APP_LDAP_SERVER_URI` must be `ldaps://`
  (validated at startup); passwords are never compared locally or logged.
- **Group authorization**: a user must belong to `APP_LDAP_REQUIRED_GROUP_DN`,
  directly or via nested groups, to be authorized — nested membership is
  resolved with a client-side, depth-capped, cycle-safe walk over each group's
  own `memberOf` attribute (not AD's server-side matching-rule extension,
  which isn't exercisable by `ldap3`'s mocked test strategy — see
  [docs/architecture.md](docs/architecture.md)'s Phase 6 section for why).
  Wrong credentials return a generic 401 (no username enumeration); correct
  credentials but no group membership return a distinct 403.
- **Sessions**: a custom signed cookie (`itsdangerous`, keyed off
  `APP_SECRET_KEY`) — `HttpOnly` always, `Secure` when `APP_ENVIRONMENT=production`,
  `SameSite=Lax`. `require_user` (in `app/auth/dependencies.py`) redirects an
  unauthenticated request to `/login?next=<original path>`, so the user lands
  back where they were headed after signing in.
- **CSRF**: `app/core/security.py` implements a double-submit cookie, used by
  both `/login` and `/logout` — FastAPI has no built-in CSRF protection, unlike
  Django.
- **Config**: see the `APP_LDAP_*` and `APP_SESSION_MAX_AGE_SECONDS` entries in
  `.env.example`. Real credentials are environment-variable-only, never
  committed, per CLAUDE.md.

## Running tests

```bash
pytest
```

The Postgres-backed integration tests (`tests/integration/test_database.py`,
`test_dashboard.py`, `test_alembic_migrations.py`) skip themselves automatically when
`TEST_DATABASE_URL` is unset or unreachable. To exercise them for real, point it at a
disposable database (never a real dev/prod one — the migration tests create and drop
tables):

```bash
TEST_DATABASE_URL=postgresql+psycopg2://phishing_analyzer:change-me@localhost:5432/phishing_analyzer_test pytest
```

## Code quality

```bash
ruff check .
black --check .
mypy app
```

`.github/workflows/ci.yml` runs `ruff`, `black --check`, `mypy`, and `pytest` on every
push/PR to `main`/`develop`.

Every phishing-detection rule in `app/phishing_detection/rules/` must have a
corresponding test under `tests/unit/`. A feature is not considered complete until its
tests pass — see [CLAUDE.md](CLAUDE.md).
