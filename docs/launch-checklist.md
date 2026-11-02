# Phase 10 — Deployment & Portfolio Launch Checklist

## Product and demo

- [ ] Review the UI on desktop, tablet and mobile widths.
- [ ] Use only synthetic, non-confidential sample code in screenshots and demos.
- [ ] Create a dedicated demo account; never publish an administrator credential.
- [ ] Confirm demo data is clearly labelled and removable.
- [ ] Capture screenshots only after testing the exact build being published.
- [ ] Add a short walkthrough showing direct code review, repository scan, remediation and report export.

## Repository hygiene

- [ ] Confirm `.env`, private keys, database files, backups and tokens are not tracked.
- [ ] Review `git diff` and `git status` before committing.
- [ ] Run `pytest -q` and `ruff check app tests alembic`.
- [ ] Run `python -m compileall -q app scripts`.
- [ ] Run `node --check app/static/app.js` where Node.js is available.
- [ ] Inspect the generated ZIP and ensure it contains no secrets or local database.
- [ ] Add an explicit open-source license only after choosing its terms.

## Staging deployment

- [ ] Provision PostgreSQL and a supported Linux host.
- [ ] Set unique `JWT_SECRET` and `POSTGRES_PASSWORD` in a secret manager or protected host environment.
- [ ] Configure exact `CORS_ORIGINS` and `TRUSTED_HOSTS` values.
- [ ] Terminate HTTPS at a trusted reverse proxy and verify certificate renewal.
- [ ] Restrict network access to PostgreSQL and the application container.
- [ ] Take a backup before applying migrations.
- [ ] Start services and inspect logs for successful migrations.
- [ ] Run `scripts/smoke_test.py` against the public HTTPS origin.
- [ ] Test registration, login, logout, code review, history access and report export.
- [ ] Verify account isolation using two separate test users.
- [ ] Verify GitHub and AI integrations only with scoped test credentials.
- [ ] Test a database restore in a separate environment.

## Production approval

- [ ] Review privacy notice, retention policy and third-party AI/GitHub data handling.
- [ ] Complete an independent security review / penetration test.
- [ ] Configure centralized logs, alerting, uptime monitoring and backup retention.
- [ ] Establish incident response and credential rotation procedures.
- [ ] Confirm support ownership, availability targets and rollback procedure.

**Release gate:** do not describe the system as production-ready solely because automated tests pass. Production approval requires deployment-specific security, privacy, backup/restore and operational verification.
