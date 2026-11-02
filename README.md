<<<<<<< HEAD
# CodeGuard AI v0.8.0

AI-assisted multi-language code review and test-suggestion platform built with FastAPI. Phase 6 adds production-readiness foundations: Alembic migrations, revocable sessions, request throttling, security headers, readiness checks and a hardened container image. The existing GitHub App, PR comment workflow, teams, admin tools and audit trail remain part of the project.

## Features

- Multi-language source review through the web UI and REST API (Python, JavaScript/TypeScript, Java, PHP, SQL and HTML).
- Static analysis for selected risky and maintainability patterns.
- Hybrid AI review through OpenAI, Google Gemini or local Ollama.
- Automatic provider fallback and per-request provider selection.
- AI findings, suggested code rewrite and generated pytest module (advisory only).
- GitHub pull-request review for changed Python files, with optional GitHub App installation authentication.
- Pull-request inline comment drafts and explicit publishing approval (GitHub `COMMENT` event only).
- Team creation, membership and shared repository registry.
- Admin dashboard for user/role management, team administration and audit activity.
- Account registration and sign-in with Argon2 password hashing.
- Short-lived signed bearer tokens; logout and password changes revoke active sessions.
- PostgreSQL persistence, versioned with Alembic migrations.
- Per-user review history and audit events.
- API request throttling, request-size guard, security headers and database readiness checks.
- Docker Compose, non-root container user, health check, Swagger (non-production), pytest and GitHub Actions CI.

## Security, privacy and deployment boundaries

- Submitted source code is parsed and inspected; it is never executed. Generated tests are not executed by this service.
- Review results are stored in the database, including findings and AI output. Source code submitted to the standalone review endpoint is not stored. GitHub PR results store review output, not the GitHub token.
- If AI review is enabled, source code may be sent to the selected AI provider. Only use repositories and source code you are authorized to share.
- GitHub PR analysis does not change repository content. Publishing comments is a separate, explicit action requiring `PUBLISH_COMMENTS`. CodeGuard publishes only a GitHub `COMMENT` review; it never approves, requests changes, merges or modifies source code.
- Configure HTTPS at a trusted reverse proxy/load balancer. HSTS must only be enabled when HTTPS is correctly deployed. Set `FORWARDED_ALLOW_IPS` to the exact trusted proxy IP(s), not `*` on an untrusted network.
- Use a unique random `JWT_SECRET` of at least 32 bytes, a strong PostgreSQL password, explicit CORS origins, restricted trusted hosts, secret management and tested backups.
- The built-in rate limiter is in-memory and per application process. It is suitable as a basic safeguard for a single instance, not a distributed rate-limiting solution. For multiple workers/replicas, enforce limits at the API gateway or use a shared Redis-backed limiter.
- The request-size guard uses the `Content-Length` header. Enforce request-body limits at the reverse proxy as well, including for chunked requests.
- This is a portfolio/staging implementation, not a security-certified product. Complete an independent security review, operational test and restore drill before handling sensitive production workloads.

## Run locally (SQLite)

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # On Windows, copy .env.example .env
uvicorn app.main:app --reload
```

The sample `.env.example` defaults to `ENVIRONMENT=development` and local SQLite. Copy it to `.env`; settings are loaded automatically. The application applies Alembic migrations at startup. Open:

- Web app: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

Create an account from the web page. Passwords must be at least 12 characters.

## PostgreSQL with Docker Compose

1. Copy `.env.example` to `.env`.
2. Set a unique random `JWT_SECRET` (at least 32 bytes) and a strong `POSTGRES_PASSWORD`.
3. Set `CORS_ORIGINS` to the actual browser origins and `TRUSTED_HOSTS` to the actual host names.
4. Set `FORWARDED_ALLOW_IPS` to the IP address(es) of the reverse proxy if it forwards client IP/protocol headers. Do not trust arbitrary forwarded headers.
5. Set `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD` to create the initial administrator on first startup, if required.
6. Set `ENVIRONMENT=production`; Compose also sets this for the application container.
7. Start services:

```bash
docker compose up --build -d
docker compose logs -f codeguard
```

The database is persisted in the `codeguard_pgdata` Docker volume. The application container runs as a non-root user and has a readiness health check. The app service binds to `127.0.0.1:8000` on the host and should be placed behind an HTTPS reverse proxy; do not expose the container directly to the public internet without a properly secured ingress layer. `ENABLE_HSTS=true` is configured for the Compose production profile. The proxy must terminate HTTPS and forward requests only from trusted addresses.

## Database migrations

Alembic is configured in `alembic.ini`; migration scripts live in `alembic/versions/`. Startup runs `alembic upgrade head` automatically. You can also run migrations manually from the project root:

```bash
alembic current
alembic history
alembic upgrade head
```

Back up PostgreSQL before deploying a new version. Test upgrades against a restored copy of production data first. Do not edit an already-applied migration; add a new revision. The initial Phase 6 migration is designed to create missing tables on a new database and add the session-version column to an existing Phase 5 database.

## Authentication and session management

- `POST /api/v1/auth/register` creates a `developer` account. Public registration cannot assign an administrator role.
- `POST /api/v1/auth/login` returns a bearer token.
- `GET /api/v1/auth/me` returns the current account.
- `POST /api/v1/auth/logout` increments the account token version and invalidates existing access tokens.
- `POST /api/v1/auth/change-password` requires the current password and a new password of at least 12 characters; it invalidates all existing sessions.
- `GET /api/v1/auth/admin-check` is administrator-only.
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` optionally bootstrap the initial administrator. Existing users are not silently promoted on later restarts.
- `ACCESS_TOKEN_MINUTES` controls token lifetime (30 minutes in the sample configuration).

Tokens are bearer credentials: protect them in transit and do not place them in URLs or logs. The browser stores the access token in session storage and calls the logout endpoint before clearing it when possible.

## Operations and environment variables

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development`, `test`, `staging` or `production` |
| `DATABASE_URL` | PostgreSQL URL for deployment; SQLite for local development |
| `JWT_SECRET` | Random signing secret; production validation rejects placeholders and short values |
| `ACCESS_TOKEN_MINUTES` | Access token lifetime |
| `CORS_ORIGINS` | Comma-separated exact trusted browser origins |
| `TRUSTED_HOSTS` | Comma-separated allowed Host header values |
| `RATE_LIMIT_PER_MINUTE` | General API limit per client IP and process |
| `AUTH_RATE_LIMIT_PER_MINUTE` | Login/registration limit per client IP and process |
| `MAX_REQUEST_BODY_BYTES` | Maximum accepted declared request body size |
| `ENABLE_HSTS` | Adds HSTS header; enable only behind correctly configured HTTPS |
| `FORWARDED_ALLOW_IPS` | Exact trusted proxy addresses for forwarded headers |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Optional first-run admin bootstrap |

In production, startup fails if the signing secret or PostgreSQL password is weak/placeholder, PostgreSQL is not configured, CORS origins or trusted hosts are missing/wildcarded, or HSTS is disabled.

## Configure AI providers (optional)

```env
AI_FALLBACK_ORDER=openai,gemini,ollama
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5-coder:7b
```

Without an AI key, static analysis and test suggestions remain available.

## GitHub integration

### Personal access token

Use a fine-grained GitHub token restricted to the selected repository. Grant Contents: read and Pull requests: read for analysis. Grant Pull requests: write only if you intend to publish review comments. The token is supplied per request and is not persisted.

### GitHub App (optional)

Configure `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY` in `.env`. Install the App only on intended repositories. Grant Contents: read and Pull requests: read for analysis. Add Pull requests: write only if the team intends to publish comments. CodeGuard creates a short-lived installation token for each request and does not store it.

### Publishing pull-request comments

Preview the proposed comments, provide a token or GitHub App installation ID with Pull requests: write, type `PUBLISH_COMMENTS` exactly and submit. GitHub receives a review event of `COMMENT`. CodeGuard does not submit approvals or change-request reviews. GitHub can reject comments if the PR diff has moved since review; re-run the review against the latest PR.

## Teams and administration

Administrators can create teams, add already-registered users, share repositories owned by CodeGuard accounts, view users and audit events, and change user roles. Team members can view their teams and shared repositories. Team membership does not bypass GitHub permissions; users still need a suitable token or configured GitHub App installation.

Useful endpoints include `GET /api/v1/admin/teams`, `POST /api/v1/admin/teams`, `POST /api/v1/admin/teams/{team_id}/members`, `POST /api/v1/admin/teams/{team_id}/repositories`, `GET /api/v1/teams`, `GET /api/v1/repositories/shared`, `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/{user_id}/role`, and `GET /api/v1/admin/audit-logs`.

## Tests and lint

```bash
pytest -q
ruff check app tests alembic
```

The CI workflow runs Ruff and pytest. Run the commands locally before pushing. If Ruff is not installed in your environment, install dependencies from `requirements.txt` first.

## Project structure

```text
app/
  api/           REST, authentication, GitHub and collaboration endpoints
  core/          token security, runtime config and middleware
  db/            SQLAlchemy engine and sessions
  models/        SQLAlchemy user, review, repository, team and audit models
  schemas/       request and response validation
  services/      analysis, AI, GitHub, auth, audit and history services
  static/        web interface
  services/      repository intelligence and dependency auditing
alembic/         versioned database migrations
tests/           automated tests
scripts/         smoke test and PostgreSQL backup/restore helpers
deploy/          sample reverse-proxy and deployment notes
demo/            synthetic code samples and demo walkthrough
docs/            architecture, security and launch documentation
.github/         GitHub Actions CI and dependency security workflow
```

## Roadmap

- Shared Redis-backed throttling and distributed session controls.
- Account recovery and optional MFA.
- Centralized monitoring, metrics, alerting and log aggregation.
- Independent penetration testing and deployment to a managed staging environment.

## License

Add a license before publishing if you want others to reuse this project.


## Phase 7 — Advanced AI Code Intelligence

### Supported language review
- Python: AST-based checks plus credential/TLS and maintainability heuristics.
- JavaScript and TypeScript: selected dynamic execution, DOM injection, and typing heuristics.
- Java: selected process execution, SQL concatenation, and deserialization heuristics.
- PHP: selected dynamic evaluation, shell execution, deserialization, legacy database API, and output handling heuristics.
- SQL: selected destructive DDL, unscoped write, wildcard selection, and predicate heuristics.
- HTML: selected inline JavaScript, iframe sandbox, and image alternative-text checks.

Non-Python checks are pattern-based and may produce false positives or miss context-dependent vulnerabilities. They are not a full compiler, parser, or commercial SAST replacement. AI provider review is advisory. Submitted code is never executed.

### Personal analytics
`GET /api/v1/analytics/overview` returns aggregate saved-review count, average score, language distribution, severity distribution, and the ten most frequent rule IDs for the authenticated user only. The dashboard displays these metrics after sign-in.

### Known scope boundary
GitHub pull-request diff ingestion remains Python-focused in this release. The multi-language selector applies to direct code submissions. Data-flow analysis and framework-aware semantic analysis are not included. Phase 8 adds bounded repository scans and dependency/SBOM analysis; Phase 9 adds security operations, remediation tracking, dashboards and reports. See `docs/repository-intelligence.md` and `docs/phase9-enterprise-security.md`.


## Phase 8 — Repository Intelligence & DevSecOps

- `POST /api/v1/github/repositories/scan` performs a bounded, read-only GitHub repository scan using a fine-grained PAT or GitHub App installation ID.
- Static heuristic checks cover supported Python, JavaScript/TypeScript, Java, PHP, SQL and HTML source files.
- Dependency parsing supports pinned requirements/project dependencies, npm lock/package files, Composer lockfiles, Maven `pom.xml`, and `go.mod` declarations.
- Exact pinned versions are queried against OSV. An unavailable OSV service is reported as unknown, never as a clean result.
- A CycloneDX 1.5 JSON SBOM is saved with the scan and downloaded through `GET /api/v1/reviews/history/{review_id}/sbom`.
- `.github/workflows/security.yml` runs Python `pip-audit` and SBOM generation, plus Node audit/SBOM generation when a package lockfile exists.

Repository scan limits: 2,500 tree entries, 30 manifests, 60 source files and 200 KB per file. Repository code is never executed. Only exact pinned dependency versions are assessed; unsupported or unpinned dependencies are omitted. Static checks may have false positives and false negatives. See `docs/repository-intelligence.md` for GitHub permissions, data flow and limitations.

## Phase 9 — Enterprise Security & Intelligence

- `GET /api/v1/security/dashboard` provides per-account scan trends, repository counts, average code-quality score, severity distribution, a heuristic risk score and remediation-state counts.
- `GET /api/v1/security/teams/{team_id}/dashboard` provides an aggregate view for repositories shared with a team. Team membership or administrator access is required.
- `GET /api/v1/security/remediations` lists findings from the user's saved repository scans. `PATCH /api/v1/security/remediations/{review_id}/{fingerprint}` tracks `open`, `in_progress`, `resolved`, `accepted_risk` or `false_positive` states with an optional note.
- `GET /api/v1/security/alerts` surfaces unresolved critical/high findings from saved scans. These are dashboard/API alerts, not email, Slack or push notifications.
- `GET /api/v1/security/reports/export?format=pdf|xlsx|csv` exports findings from the authenticated user's saved repository scans.
- `GET|POST /api/v1/security/schedules` and `DELETE /api/v1/security/schedules/{schedule_id}` manage daily/weekly schedule configuration for a registered repository.

**Scheduling boundary:** CodeGuard stores the schedule preference but does not run a background scheduler or retain GitHub credentials. An external scheduler/runner must invoke scans and supply a valid short-lived GitHub credential at execution time. The schedule record alone does not trigger scans or notifications.

The risk score is a transparent severity-weighted heuristic, not a CVSS score or compliance certification. Trend data reflects saved scan snapshots; repeated findings across scans can be counted repeatedly. Remediation states are attached to a specific scan and finding fingerprint, so a new scan may create a new remediation item. Team dashboards aggregate scans only for repositories registered and shared with that team. Reports contain saved findings and should be treated as sensitive security information.

Phase 9 adds `0002_phase9_security_intelligence` Alembic migration for remediation and schedule records. Existing databases are upgraded at startup; back up the database before deployment.


## Phase 10 — Deployment & Portfolio Launch

- Added a production environment template (`.env.production.example`) with explicit hostname, CORS, secret and HTTPS settings. Replace all placeholders before use.
- Added `deploy/nginx.conf` as a sample TLS reverse-proxy configuration. Review hostname, certificate paths, firewall rules and trusted forwarded headers for the target environment.
- Added deployment, backup and restore guidance under `deploy/` and scripts under `scripts/`. The restore helper requires explicit confirmation because it replaces the target database.
- Added `scripts/smoke_test.py` for basic liveness, readiness and dashboard HTTP checks. It is not a penetration test or complete acceptance test.
- Added a demo walkthrough and synthetic sample code under `demo/`. The examples intentionally contain unsafe patterns for demonstration and must not be used in production.
- Added `docs/launch-checklist.md` with staging, operational, privacy and production approval gates.
- Improved dashboard navigation, keyboard focus visibility, skip navigation, reduced-motion behavior and mobile layout.

**Deployment boundary:** The included Docker Compose and Nginx files are deployment starting points, not evidence of a live production deployment. A real release still requires a managed secret store, TLS/DNS, firewall review, backup-restore drill, independent security assessment, privacy review, monitoring and an authenticated staging acceptance test.


### Useful project commands

```bash
make install
make check
make lint
make run
make smoke
```

On Windows, use the equivalent Python commands in PowerShell. PostgreSQL backup/restore helpers are available as `scripts/backup_postgres.ps1` and `scripts/restore_postgres.ps1 -BackupFile <path>`.
=======
# CodeGuard-AI
AI-powered multi-language code review and security analysis platform built with FastAPI, Python, PostgreSQL and GitHub integration
>>>>>>> 32ceaea460e36273d51f8bdba6b5c095c9fb8cb1
