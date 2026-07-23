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

## Running tests

```bash
pytest
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
