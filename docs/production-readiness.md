# Phase 6 – Production Readiness Notes

## Implemented in this phase

- Alembic migration infrastructure. Startup applies `upgrade head`.
- A migration that creates missing schema objects and adds `users.token_version` to an existing Phase 5 database.
- Access-token version claims. Logout and password change increment the stored version and invalidate older tokens.
- Password change endpoint requiring the current password and a 12-character minimum new password.
- In-memory API throttling with a stricter configurable limit for login and registration.
- Declared request-size guard and baseline response security headers.
- Optional trusted-host validation and production configuration checks.
- Liveness and database readiness endpoints.
- Production Docker image runs as a non-root user and includes a readiness health check.
- Swagger/OpenAPI routes are disabled in production mode.

## Operational constraints

The built-in limiter is per-process and not shared across replicas. Use a gateway or shared Redis limiter for multi-instance deployments. The request-size middleware uses `Content-Length`; also enforce limits at the reverse proxy. HSTS is only meaningful after HTTPS is correctly terminated. Forwarded headers must be trusted only from known proxy addresses. Secrets must be supplied by a deployment secret manager and never committed.

## Deployment checklist

- [ ] PostgreSQL backup and restore tested.
- [ ] Strong random `JWT_SECRET` configured in secret storage.
- [ ] `POSTGRES_PASSWORD` configured in secret storage.
- [ ] `CORS_ORIGINS` restricted to actual UI origins.
- [ ] `TRUSTED_HOSTS` restricted to actual hostnames.
- [ ] `FORWARDED_ALLOW_IPS` restricted to reverse proxy IPs.
- [ ] HTTPS enforced at the ingress; HSTS enabled only after verification.
- [ ] Rate limits and request-body limits also enforced at ingress.
- [ ] Admin credentials set securely and rotated after bootstrap.
- [ ] AI/GitHub data-sharing permissions reviewed with repository owners.
- [ ] Migration tested against a restored copy of the target database.
- [ ] Independent security review and monitoring configured.

## Not verified in this development run

No live PostgreSQL server, Docker daemon, reverse proxy, TLS certificate, GitHub App credentials, external AI provider or production host was available for end-to-end validation. Those integrations require environment-specific staging tests.


## Phase 7 scope and limitations

Multi-language direct review supports Python, JavaScript, TypeScript, Java, PHP, SQL, and HTML. Non-Python checks are regex-based heuristics, not full parsing or semantic analysis. GitHub PR diff ingestion remains Python-focused. Personal analytics are user-scoped. No submitted code is executed.
