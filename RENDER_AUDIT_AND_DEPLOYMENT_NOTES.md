# CodeGuard AI — Audit and Render Deployment Notes

Audit basis: uploaded `CodeGuard_AI (5).zip`, Git HEAD `1611477213e20a158a58378d18f7f7372c123012`
(branch `main`; archive's local `origin/main` ref also points to this commit).

## Verification performed

- `python -m pytest -q` against a fresh temporary SQLite database: **49 passed**.
- Ruff lint/format checks were not rerun in this audit container because Ruff is not installed here.
  The previous user-reported local checks were green, but that is not a fresh verification of this archive.
- Docker image build was not run because Docker is unavailable in this environment.
- Live Render startup could not be exercised because the Render environment and its secrets are not accessible here.

## Findings

### Confirmed positive items

- The archive contains the shortened Alembic revision `0002_phase9_intel`, descending from
  `0001_phase6_security`; this avoids the earlier PostgreSQL `alembic_version.version_num`
  32-character limit.
- Startup has explicit stage markers for configuration validation, migrations, administrator
  seeding, and completion, with exception traceback output to stderr.
- Production disables interactive API documentation.
- Production config validation requires PostgreSQL, a sufficiently long JWT secret, explicit
  CORS origins and trusted hosts, a strong database password, and HSTS.
- Production registration defaults to disabled.
- Docker runs as a non-root user and uses the platform-provided `PORT`.
- `.dockerignore` excludes `.env`, local databases, virtual environments, and Git metadata.

### Issues / risks

1. **Render startup exit status 3 is not fully diagnosed by the archive alone.**
   Uvicorn exit status 3 commonly indicates an application startup failure. The lifespan has
   three failure points: runtime config validation, Alembic migration, and admin seeding.
   Earlier evidence that PostgreSQL reached Alembic revision `0002_phase9_intel` makes the
   admin-seeding stage the leading remaining suspect *if that evidence is from the same
   deployment and database*. The current archive cannot prove the exact failing stage.
2. `seed_admin()` raises an exception when `ADMIN_PASSWORD` is shorter than 12 characters.
   If an existing user has the configured `ADMIN_EMAIL`, seeding skips it and does not reset
   its role or password. Check that the Render environment variable is at least 12 characters
   and that the email belongs to an existing admin account.
3. Production config validation checks `POSTGRES_PASSWORD` separately from `DATABASE_URL`.
   They must refer to the same PostgreSQL credential. A mismatch will usually surface as a
   connection/migration failure.
4. `DATABASE_URL` must use SQLAlchemy's psycopg 3 dialect form:
   `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`.
   URL-encode reserved characters in username/password when composing the URL. Prefer the
   Render internal database URL for a service in the same region.
5. The Dockerfile healthcheck checks `/api/v1/health/ready`, which requires database access.
   This is useful after startup but is not a substitute for the Render service health-check
   configuration. Do not treat a failed health check as proof that Uvicorn itself exited.
6. CI installs all of `requirements.txt`, including test/lint packages, in the production image.
   This increases image size and attack surface. Consider separating runtime and development
   requirements after the deployment is stable.
7. The security workflow's `pip-audit` step may fail when known advisories are present; review
   its generated artifact separately from application startup failures.

## Render environment checklist

Set these in the Render Web Service environment (never commit them):

- `ENVIRONMENT=production`
- `DATABASE_URL=postgresql+psycopg://...` using the Render **internal** database URL credentials
- `POSTGRES_PASSWORD` equal to the password for that same database user
- `JWT_SECRET` generated as a random secret of at least 32 bytes
- `CORS_ORIGINS` set to the exact frontend origin(s), comma-separated; no `*`
- `TRUSTED_HOSTS` set to the exact Render hostname(s), comma-separated; no `*`
- `ENABLE_HSTS=true`
- `ALLOW_REGISTRATION=false`
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` if bootstrapping an initial admin; password >= 12 chars
- `ADMIN_FULL_NAME` optional

Do not set `PORT` manually unless the platform specifically requires it; the Docker command reads
Render's injected `PORT`.

## How to isolate the next failed startup

In Render, open the latest deployment's logs and locate the first `[STARTUP]` marker:

- No `[STARTUP] BEGIN` marker: failure likely occurs before lifespan starts (module import,
  missing package, or container command).
- `FAILED at stage: runtime configuration validation`: inspect the named environment variables
  above, without sharing their values.
- `FAILED at stage: database migrations`: check the internal URL, password match, database
  reachability, and migration error.
- `FAILED at stage: administrator seeding`: check `ADMIN_PASSWORD` length and whether the
  configured email already exists.
- `APPLICATION STARTUP COMPLETED`: startup succeeded; investigate Render health-check/path
  configuration or application routing instead.

For a safe health test after deployment:
- `/api/v1/health/live` should return HTTP 200.
- `/api/v1/health/ready` should return HTTP 200 when PostgreSQL is reachable, otherwise 503.
- `/docs` returning 404 in production is intentional because API docs are disabled.

## Clean package contents

This package intentionally excludes `.env`, `.git`, `.venv`, Python caches, local database
files, logs, and backup dumps. It retains `.env.example` and `.env.production.example` templates.
