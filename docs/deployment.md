# Deployment

Target environment: Ubuntu Server, PostgreSQL, Nginx (reverse proxy), Uvicorn
workers (managed by Gunicorn in production via
`gunicorn -k uvicorn.workers.UvicornWorker`), Windows Server 2025 Active
Directory over LDAPS, deployed via GitHub Actions.

TODO: document the concrete deployment procedure here as it is built out
(Phase 8):

- systemd unit for Gunicorn/Uvicorn
- Nginx site config (see `docker/nginx/nginx.conf` for the containerized
  equivalent)
- Environment variable / secrets provisioning on the server (see
  `.env.example` for the required variable names — never commit real values)
- GitHub Actions deploy workflow (see `.github/workflows/deploy.yml`)
- LDAPS/AD connectivity requirements (certificate trust, firewall rules,
  service account permissions)

Per CLAUDE.md, this file must be updated in the same PR as any change to
deployment/infrastructure.
