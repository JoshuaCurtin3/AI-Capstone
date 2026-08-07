# AGENTS.md

Guidance for Codex (and other agents) working in this repository.

## Project overview

A FastAPI-based phishing email analyzer, deployed on Ubuntu Server with:

- **Backend**: FastAPI (Python), ASGI
- **Templates / UI**: Jinja2 templates + Bootstrap (server-rendered, no SPA framework)
- **Database**: PostgreSQL, accessed via SQLAlchemy; schema changes via Alembic migrations
- **Web server / app server**: Nginx (reverse proxy) + Uvicorn workers (managed by Gunicorn
  in production, `gunicorn -k uvicorn.workers.UvicornWorker`)
- **Authentication**: Windows Server 2025 Active Directory via LDAPS (no local password auth)
- **CI/CD**: GitHub Actions handles build, test, and deployment
- **AI assistance**: Codex API is used only to generate a human-readable explanation of
  an analysis result. It never computes, adjusts, or influences the numerical risk score.

> Note: this project originally scaffolded as Django (see git history / TASKS.md Phase 1).
> It has since been redirected to FastAPI + SQLAlchemy + Alembic. The Django-specific
> `app/` tree from that earlier scaffold is superseded and will be replaced — see TASKS.md
> for the migration plan.

## Core architectural rule — read this first

**The phishing risk score is produced exclusively by a deterministic, rule-based scoring
engine written in Python.** This is the most important constraint in the project:

- The scoring engine must be pure and deterministic: same email input → same score, every
  time, with no calls to an LLM, no randomness, and no hidden state.
- Codex API may be called *after* a score has already been computed, and only to turn the
  triggered rules/signals into a human-readable explanation string. The explanation is
  cosmetic — it must never be parsed back into the score, used as a tiebreaker, or allowed
  to override/adjust the numeric result in any way.
- If a change would let any LLM output feed back into the score (directly or indirectly,
  e.g. via a "confidence adjustment" or "AI review" step), stop and flag it — do not
  implement it without explicit confirmation.
- Every scoring rule lives in the scoring engine module and must be independently unit
  tested (see Testing below). Do not add a new rule without a corresponding test.

## Repository structure

The repo uses a hybrid layout under `app/`: a shared horizontal layer
(`config/`, `core/`, `database/`, `models/`, `schemas/`, `services/`,
`utils/`) plus vertical domain packages (`auth/`, `api/`, `email_parser/`,
`phishing_detection/`, `ai_analysis/`), each owning its own SQLAlchemy models,
Pydantic schemas, and services. `phishing_detection/` contains the
deterministic scoring engine described above; `ai_analysis/` is the only
place Codex API calls are made, and only for explanation text. Full
rationale and a feature-placement guide live in
[docs/architecture.md](docs/architecture.md) — read it before adding a new
top-level directory. **This structure is being rebuilt for FastAPI** — see
TASKS.md Phase 1 for the current state of that migration.

## Branching strategy

- `main` — production-ready code only. Deployed via GitHub Actions.
- `develop` — integrated development work; feature branches merge here first.
- `feature/*` — individual features/fixes, branched off `develop`, merged back via PR.

Do not commit directly to `main` or `develop`; work happens on `feature/*` branches.

## Development workflow requirements

- **Small, reviewable changes.** Prefer several small PRs/commits over one large change.
  Each change should do one thing and be easy to review in isolation.
- **Tests for every analysis rule.** Every phishing-detection rule/heuristic in the scoring
  engine needs its own test case(s) covering at least: a clear true-positive trigger, a
  clear true-negative (non-trigger), and any documented edge case for that rule.
- **A feature is not "done" until its tests pass.** Never mark a task, TODO, or plan step
  complete while tests are failing, skipped, or not yet written. Run the test suite before
  reporting completion.
- **No secrets in source control.** No API keys, LDAP bind credentials, database
  passwords, app secret keys, or certificates in the repo, in code, or in commit history.
  All secrets are supplied via environment variables (or a secrets manager) and read
  through a typed settings object (e.g. `pydantic-settings`) at runtime.
- **Environment variables for configuration.** Anything that differs between dev, CI, and
  production (DB connection info, allowed hosts/origins, LDAP/AD settings, Codex API key,
  Uvicorn/Gunicorn/Nginx settings, debug flags) must be configurable via environment
  variables, never hardcoded.
- **Secure defaults.** Debug/reload mode off outside local dev, secret keys and DB
  credentials from the environment only, allowed hosts/CORS origins explicitly set (no
  wildcard `*` in production), HTTPS/HSTS and secure cookie flags enabled in production,
  CSRF protection on any session-authenticated form endpoint (FastAPI has no built-in CSRF
  protection — this must be added explicitly, e.g. via middleware, for the login/session
  flow), and dependencies kept current. Don't weaken any of these to make something "just
  work" — fix the underlying config instead.
- **Type hints.** All new/modified Python functions and methods should have type hints on
  parameters and return values.
- **Clear comments.** Comment the *why*, not the *what* — especially around scoring rule
  thresholds, LDAPS/AD integration quirks, and anything security-sensitive. Avoid restating
  what the code obviously does.
- **Documentation updates with infrastructure changes.** Any change touching deployment,
  Nginx/Uvicorn/Gunicorn config, PostgreSQL/Alembic setup, LDAPS/AD integration, or GitHub
  Actions workflows must come with a corresponding update to the relevant docs in the same
  PR.

## Testing

- Run the full test suite (`pytest`) before considering any task complete.
- Scoring engine rules require dedicated unit tests; do not rely on integration tests alone
  to cover rule-level logic.
- API endpoint tests use FastAPI's `TestClient`/`httpx`; async code paths use
  `pytest-asyncio`.
- When mocking the Codex API in tests, only mock the explanation-generation call — never
  design a test in a way that implies Codex is part of the scoring path.

## Authentication notes

- User authentication goes through LDAPS against Windows Server 2025 Active Directory.
  Do not introduce a parallel local-auth path or store AD passwords locally.
- Treat LDAPS connection settings (server, bind DN, bind password, base DN) as secrets —
  environment variables only, never committed.

## What to avoid

- Do not let any LLM-generated content influence, adjust, or gate the numerical risk score.
- Do not commit `.env` files, credentials, certificates, or API keys.
- Do not disable security middleware/settings (CORS, trusted host, CSRF, secure cookies)
  to unblock local testing without reverting before merge.
- Do not mark work complete with failing, skipped, or missing tests.
