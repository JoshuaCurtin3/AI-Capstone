# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## Project overview

A Django-based phishing email analyzer, deployed on Ubuntu Server with:

- **Database**: PostgreSQL
- **Web server / app server**: Nginx (reverse proxy) + Gunicorn (WSGI)
- **Authentication**: Windows Server 2025 Active Directory via LDAPS (no local password auth)
- **CI/CD**: GitHub Actions handles build, test, and deployment
- **AI assistance**: Claude API is used only to generate a human-readable explanation of
  an analysis result. It never computes, adjusts, or influences the numerical risk score.

## Core architectural rule — read this first

**The phishing risk score is produced exclusively by a deterministic, rule-based scoring
engine written in Python.** This is the most important constraint in the project:

- The scoring engine must be pure and deterministic: same email input → same score, every
  time, with no calls to an LLM, no randomness, and no hidden state.
- Claude API may be called *after* a score has already been computed, and only to turn the
  triggered rules/signals into a human-readable explanation string. The explanation is
  cosmetic — it must never be parsed back into the score, used as a tiebreaker, or allowed
  to override/adjust the numeric result in any way.
- If a change would let any LLM output feed back into the score (directly or indirectly,
  e.g. via a "confidence adjustment" or "AI review" step), stop and flag it — do not
  implement it without explicit confirmation.
- Every scoring rule lives in the scoring engine module and must be independently unit
  tested (see Testing below). Do not add a new rule without a corresponding test.

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
  passwords, Django `SECRET_KEY`, or certificates in the repo, in code, or in commit
  history. All secrets are supplied via environment variables (or a secrets manager) and
  read through `os.environ` / `django-environ` at runtime.
- **Environment variables for configuration.** Anything that differs between dev, CI, and
  production (DB connection info, `ALLOWED_HOSTS`, LDAP/AD settings, Claude API key,
  Gunicorn/Nginx settings, `DEBUG`) must be configurable via environment variables, never
  hardcoded.
- **Secure Django defaults.** `DEBUG = False` outside local dev, `SECRET_KEY` from the
  environment, `ALLOWED_HOSTS` explicitly set, HTTPS/HSTS and secure cookie settings
  enabled in production, CSRF protection on, and dependencies kept current. Don't weaken
  any of these to make something "just work" — fix the underlying config instead.
- **Type hints.** All new/modified Python functions and methods should have type hints on
  parameters and return values.
- **Clear comments.** Comment the *why*, not the *what* — especially around scoring rule
  thresholds, LDAPS/AD integration quirks, and anything security-sensitive. Avoid restating
  what the code obviously does.
- **Documentation updates with infrastructure changes.** Any change touching deployment,
  Nginx/Gunicorn config, PostgreSQL setup, LDAPS/AD integration, or GitHub Actions workflows
  must come with a corresponding update to the relevant docs in the same PR.

## Testing

- Run the full test suite before considering any task complete.
- Scoring engine rules require dedicated unit tests; do not rely on integration tests alone
  to cover rule-level logic.
- When mocking the Claude API in tests, only mock the explanation-generation call — never
  design a test in a way that implies Claude is part of the scoring path.

## Authentication notes

- User authentication goes through LDAPS against Windows Server 2025 Active Directory.
  Do not introduce a parallel local-auth path or store AD passwords locally.
- Treat LDAPS connection settings (server, bind DN, bind password, base DN) as secrets —
  environment variables only, never committed.

## What to avoid

- Do not let any LLM-generated content influence, adjust, or gate the numerical risk score.
- Do not commit `.env` files, credentials, certificates, or API keys.
- Do not disable Django security middleware/settings to unblock local testing without
  reverting before merge.
- Do not mark work complete with failing, skipped, or missing tests.
