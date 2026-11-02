# CodeGuard AI — Architecture (v0.8.0)

## Request flow

1. Browser or API client submits a Python filename and source text.
2. FastAPI validates the request using Pydantic.
3. The static analyzer parses the AST and checks a small set of rules.
4. The test suggester extracts public function names and proposes test cases.
5. If configured, the AI adapter requests an advisory review from an LLM provider.
6. The service calculates a deterministic score from static findings and returns JSON.

## Components

- `api/routes.py`: HTTP endpoints.
- `schemas/review.py`: request and response contracts.
- `services/analyzer.py`: AST-based static rules.
- `services/test_suggester.py`: test-name suggestions.
- `services/ai_reviewer.py`: optional LLM integration.
- `services/review_service.py`: orchestration and scoring.
- `static/`: browser-based user interface.

## Trust boundaries

Submitted source code is untrusted. This version never executes it. AI provider requests may transmit submitted code to the configured provider; configure this deliberately and avoid confidential source. Authentication, request throttling, request-size checks, security headers and restricted CORS are implemented. Production still requires HTTPS ingress, centralized logging with secret redaction, privacy controls, provider-specific data governance and an independent security review.


## Hybrid AI provider layer

`services/ai_providers.py` implements a provider adapter:
- OpenAI uses the OpenAI chat-completions API.
- Gemini uses the Gemini generateContent API.
- Ollama uses its OpenAI-compatible local endpoint.

In `auto` mode, providers are attempted in `AI_FALLBACK_ORDER`. A successful provider response is parsed and validated against the `AIReview` schema. Provider errors are summarized without exposing credentials. AI output is advisory and never executed.


## GitHub pull-request review and comment publishing

The GitHub service retrieves pull-request metadata, file changes and source content at the PR head SHA. It analyses Python files only and filters static findings to added lines when patch data is available. It never checks out or executes repository code. A supplied personal access token or short-lived GitHub App installation token is used only for the request and is not stored. AI review may transmit source to the configured provider. Comment drafts are generated separately and are published only after the caller explicitly supplies the `PUBLISH_COMMENTS` confirmation; publishing uses GitHub's `COMMENT` event and never approves or requests changes.


## Phase 4: identity and persistence

The API uses signed JWT bearer tokens and Argon2 password hashes. Public registration always creates the `developer` role. An administrator can be bootstrapped at startup using `ADMIN_EMAIL` and `ADMIN_PASSWORD`; credentials are not embedded in source. Protected review endpoints derive the account from the token, then persist structured review output under that account.

SQLAlchemy supports PostgreSQL through psycopg and SQLite for local development. The `users` table stores account identity, password hash, role and activation state. The `reviews` table stores review identifiers, ownership, type, repository/file metadata, score, summary, structured result JSON and creation time. Source code is deliberately not included in the saved review record. GitHub tokens are request-only.

History queries are scoped to the authenticated user. Review detail lookup returns 404 for records outside the caller's ownership. The admin-check route demonstrates role enforcement. Schema changes are versioned with Alembic. Startup applies `alembic upgrade head`; back up the database and test each migration against a restored copy before deployment.

A `repositories` table holds each user's GitHub owner, repository name and default branch, with a per-user uniqueness constraint. It intentionally does not store personal access tokens. The history API offers a generated-test download route for reviews containing an AI-generated pytest module; generated tests remain unexecuted and must be reviewed before use.


## Phase 5: GitHub collaboration and audit

Optional GitHub App authentication signs short-lived App JWTs and exchanges them for installation access tokens. Installation tokens are held only in request memory. A personal access token remains supported for development and single-repository use.

A saved GitHub pull-request review can produce line-specific comment drafts. Publishing is a separate endpoint, requires the literal confirmation `PUBLISH_COMMENTS`, and sends a GitHub review event of `COMMENT`. The implementation does not submit `APPROVE` or `REQUEST_CHANGES`. GitHub can reject comments when the diff no longer matches the saved head SHA/line positions; users should rerun the review for a changed PR.

Teams, memberships and team-repository links are stored in dedicated tables. Administrators create teams, add registered users, share repositories, manage developer/admin roles and inspect audit events. Team membership does not grant GitHub access by itself; GitHub App installation permissions or a suitable token are still required.

Audit events record authentication, reviews, repository changes, team membership/sharing, role updates and published comment metadata. Tokens and private keys are not written to audit records.


## Phase 6: production-readiness foundations

The application applies Alembic migrations during startup. The initial Phase 6 revision supports a fresh database and an existing Phase 5 schema, adding `users.token_version` to existing accounts. JWTs carry the account token version; logout and password change increment the database value so previously issued tokens are rejected. Password changes require the current password and a new password of at least 12 characters.

`SecurityAndRateLimitMiddleware` applies per-process request throttling, a declared content-length limit, request IDs and baseline security headers. Login and registration have a separate stricter threshold. This limiter is intentionally documented as a single-process safeguard; multi-instance deployments must use a shared gateway or Redis-backed limiter. Reverse proxies must enforce request size limits too, and forwarded headers must only be trusted from configured proxy addresses.

Operations endpoints separate liveness (`/api/v1/health/live`) from readiness (`/api/v1/health/ready`), where readiness checks database connectivity. Production mode disables Swagger/OpenAPI and validates the JWT secret, PostgreSQL URL, CORS origins, trusted hosts, database password and HSTS setting. The Docker image runs as a non-root user and includes a readiness health check. HTTPS termination, backups, monitoring, secret management and independent security testing remain deployment responsibilities.


## Phase 7 intelligence layer

Direct code submissions dispatch to a language-aware analyzer. Python uses the existing AST analyzer; JavaScript, TypeScript, Java, PHP, SQL, and HTML use explicitly documented pattern heuristics. The analytics endpoint aggregates only the authenticated user's persisted review records and does not expose cross-user metrics. GitHub PR diff analysis remains Python-focused.


## Phase 9 security operations

Phase 9 adds user-scoped remediation state, security dashboards, team aggregation over shared repository scans, high-severity alert views, PDF/XLSX/CSV report export and schedule configuration. Schedule execution is intentionally external: CodeGuard does not store GitHub credentials or run a background scheduler. See `phase9-enterprise-security.md`.
