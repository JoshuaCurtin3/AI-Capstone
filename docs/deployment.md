# Deployment

Target environment: Ubuntu Server, PostgreSQL, Nginx (reverse proxy), Uvicorn
workers (managed by Gunicorn in production via
`gunicorn -k uvicorn.workers.UvicornWorker`), Windows Server 2025 Active
Directory over LDAPS, deployed via GitHub Actions.

## Current state: manually-provisioned Ubuntu VM (pre-Phase 8)

Ahead of Phase 8's containerized deployment plan, the target Ubuntu Server VM
has already been manually provisioned (not via Docker Compose):

- Windows Server 2025 AD domain (`project.local`); the Ubuntu VM is
  domain-joined.
- PostgreSQL installed, with the `phishing_analyzer` database and its
  database role already created.
- Application cloned to `/opt/phishing-analyzer`, with a Python virtual
  environment and dependencies installed.
- FastAPI running under systemd.
- Nginx reverse-proxying to it on port 80.

### Applying Phase 5 (database) to this VM

Every command below runs **on the VM**, from `/opt/phishing-analyzer`, with
the venv activated. Substitute the actual systemd unit name if it differs
from the placeholder `phishing-analyzer.service` used here.

```bash
cd /opt/phishing-analyzer
source .venv/bin/activate

# 1. Install the new Phase 5 dependencies (sqlalchemy, psycopg2-binary, alembic)
pip install -r requirements.txt

# 2. Add APP_DATABASE_URL (and, if not already present, the APP_LDAP_*/
#    APP_SESSION_* vars from .env.example) to the VM's .env file. Never
#    commit this file - see CLAUDE.md.
#    Example line to add/update in /opt/phishing-analyzer/.env:
#    APP_DATABASE_URL=postgresql+psycopg2://<db_role>:<password>@localhost:5432/phishing_analyzer

# 3. Apply the Phase 5 migration - creates users/analysis_results/triggered_rules.
alembic upgrade head

# 4. Restart the app so it picks up the new dependencies/env var.
sudo systemctl restart phishing-analyzer.service

# 5. Verify.
curl -s http://127.0.0.1/health
```

If step 3 fails with a connection error, double-check the `phishing_analyzer`
database role's password matches `APP_DATABASE_URL` and that PostgreSQL is
listening on the expected host/port (`sudo -u postgres psql -c "\du"` to list
roles, `sudo systemctl status postgresql` to confirm the service is up).

**Rollback**, if ever needed: `alembic downgrade base` reverses the Phase 5
schema (drops `users`/`analysis_results`/`triggered_rules`) cleanly - both
directions were verified in `tests/integration/test_alembic_migrations.py`.

### Applying Phase 6 (Active Directory authentication) to this VM

**Status as of 2026-07-28: application code is complete and merged; none of the
steps below have been done yet.** Windows Server 2025 is already the `project.local`
domain controller and Ubuntu has joined that domain and can resolve/communicate with
it, but LDAPS itself has not been configured or tested. Do these in order — each
depends on the one before it.

**On the Windows Server 2025 domain controller (`project.local`):**

1. **Issue/bind a valid LDAPS certificate.** AD LDAPS requires a certificate whose
   Subject/SAN matches the domain controller's FQDN, trusted by (or issued from) a CA
   the domain controller trusts — typically via Active Directory Certificate Services
   (a "Domain Controller" or "Kerberos Authentication" template) or an enterprise CA.
   Without this, port 636 will not accept TLS connections at all.
2. **Verify LDAPS is actually listening on TCP 636** — from the domain controller
   itself:
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 636
   ```
   and from the Ubuntu VM, once the cert is in place:
   ```bash
   openssl s_client -connect dc.project.local:636 -showcerts </dev/null
   ```
   A successful TLS handshake (not a connection refusal/reset) confirms this step.
3. **Create a dedicated, read-only LDAP service account** (e.g.
   `svc-phishing-app`) in Active Directory Users and Computers. It only ever needs to
   *search* — it must never need write access, and should not be a member of any
   privileged group (Domain Admins, etc.). This becomes `APP_LDAP_BIND_DN` /
   `APP_LDAP_BIND_PASSWORD`.
4. **Create the authorized application security group** (e.g.
   `PhishingAnalyzer-Users`) — its DN becomes `APP_LDAP_REQUIRED_GROUP_DN`. Only
   members of this group (directly, or via a nested group — see
   `docs/architecture.md`'s Phase 6 section) will be able to log in.
5. **Add test users to that group** — at least one member (for the "successful
   login" test below) and confirm at least one real AD user who is deliberately
   **not** a member (for the "unauthorized" test below).

**On the Ubuntu VM** (`/opt/phishing-analyzer`, venv activated):

6. **Configure the real LDAP values in `.env`** (never commit this file — see
   CLAUDE.md). Fill in the real DNs/password for the values `.env.example` only shows
   as placeholders:
   ```bash
   APP_LDAP_SERVER_URI=ldaps://dc.project.local:636
   APP_LDAP_BIND_DN=CN=svc-phishing-app,OU=Service Accounts,DC=project,DC=local
   APP_LDAP_BIND_PASSWORD=<the real service account password>
   APP_LDAP_USER_SEARCH_BASE_DN=OU=Users,DC=project,DC=local
   APP_LDAP_REQUIRED_GROUP_DN=CN=PhishingAnalyzer-Users,OU=Groups,DC=project,DC=local
   ```
7. **Trust the domain controller's certificate, if it isn't issued by a CA Ubuntu
   already trusts** (self-signed or an internal enterprise CA not in the system trust
   store):
   ```bash
   sudo cp dc-project-local.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates
   ```
   The app never disables certificate verification to work around a missing trust
   relationship — this step is required, not optional, if the handshake in step 2
   fails from Ubuntu.
8. **Deploy the final code**:
   ```bash
   cd /opt/phishing-analyzer
   git pull
   source .venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head   # Phase 5 - if not already applied
   sudo systemctl restart phishing-analyzer.service
   curl -s http://127.0.0.1/health
   ```
9. **Perform live tests** against the real domain controller — through Nginx, not
   just `curl http://127.0.0.1`, so the full request path is exercised:
   - **Successful login**: a user who *is* in `PhishingAnalyzer-Users` signs in at
     `/login` with their real AD password → redirected, session cookie set.
   - **Failed login**: a valid username with the wrong password → generic
     "Invalid username or password." (401), no session cookie set.
   - **Unauthorized login**: a valid AD user who is *not* in the required group,
     correct password → distinct "not authorized" (403), no session cookie set.
   - **Session**: after a successful login, `GET /account` and `GET /dashboard` both
     return 200 without re-authenticating; the session cookie is `HttpOnly`/`Secure`
     (confirm `APP_ENVIRONMENT=production` in `.env` so `Secure` is actually set) —
     inspect via the browser's dev tools, not just that the page loads.
   - **Logout**: `POST /logout` clears the session; a follow-up `GET /account` bounces
     back to `/login?next=/account`.

If step 2's handshake fails, the problem is almost always the certificate (step 1) or
firewall — check `sudo journalctl -u <the AD/LDAP-facing service>` on the domain
controller and confirm nothing is blocking TCP 636 between the two VMs.

## Future state (Phase 8+): containerized deployment

TODO: document the container-based deployment procedure here as it is built
out (Phase 8) - this will eventually replace the manual VM setup above:

- systemd unit for Gunicorn/Uvicorn (or its container equivalent)
- Nginx site config (see `docker/nginx/nginx.conf` for the containerized
  equivalent)
- Environment variable / secrets provisioning on the server (see
  `.env.example` for the required variable names — never commit real values)
- GitHub Actions deploy workflow (see `.github/workflows/deploy.yml`)
- LDAPS/AD connectivity requirements (certificate trust, firewall rules,
  service account permissions) - see docs/architecture.md's Authentication
  section for what the app itself already enforces (LDAPS-only, etc.)

Per CLAUDE.md, this file must be updated in the same PR as any change to
deployment/infrastructure.
