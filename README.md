# AI-Capstone — Phishing Email Analyzer

A Django web application that analyzes submitted emails and produces a phishing risk
score. The risk score is always computed by a deterministic, rule-based scoring engine;
the Claude API is used only to turn an already-computed score into a human-readable
explanation. See [CLAUDE.md](CLAUDE.md) for the full set of project rules and
[docs/architecture.md](docs/architecture.md) for the detailed structure of this repo.

## Stack

- **Backend**: Django
- **Database**: PostgreSQL
- **App server**: Gunicorn, reverse-proxied by Nginx
- **Auth**: Windows Server 2025 Active Directory over LDAPS
- **AI**: Claude API (explanation generation only, never scoring)
- **CI/CD**: GitHub Actions
- **Host**: Ubuntu Server

## Repository layout

```
app/                    Django project package (source root)
  config/               Settings, root URLconf, WSGI/ASGI entry points
  core/                 Cross-cutting concerns: exceptions, middleware, logging
  database/             DB-level helpers not tied to a specific domain (routers, etc.)
  models/               Shared/abstract model mixins used across domain apps
  schemas/              Shared data-validation base classes/types
  services/             Cross-domain orchestration (e.g. the end-to-end analysis pipeline)
  auth/                 Django app: LDAPS/Active Directory authentication backend
  api/                  Django app: HTTP routing layer (thin, delegates to services)
  email_parser/         Django app: parses raw email input into structured data
  phishing_detection/   Django app: the deterministic risk-scoring engine
  ai_analysis/          Django app: Claude API explanation generation
  templates/            Shared Django templates
  static/               Shared static assets (css/js/images)
  utils/                Small generic, domain-agnostic helpers
tests/                  unit/, integration/, fixtures/ (mirrors app/ by domain)
docs/                   Architecture, deployment, and scoring-rule documentation
scripts/                Local dev and deployment helper scripts
docker/                 Nginx and Gunicorn configuration used by the containers
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
python manage.py migrate
python manage.py runserver
```

## Running tests

```bash
pytest
```

Every phishing-detection rule in `app/phishing_detection/rules/` must have a
corresponding test under `tests/unit/`. A feature is not considered complete until its
tests pass — see [CLAUDE.md](CLAUDE.md).
