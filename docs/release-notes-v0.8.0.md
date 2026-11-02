# CodeGuard AI v0.8.0

## Portfolio release

This release packages the Phase 10 deployment and portfolio-launch work.

### Highlights
- Multi-language direct code review with static checks and optional AI-provider review.
- GitHub pull-request analysis with separately confirmed comment publishing.
- Bounded, read-only repository scans and dependency intelligence.
- CycloneDX 1.5 SBOM generation and download.
- Security dashboards, remediation tracking, team views, and PDF/XLSX/CSV exports.
- Authentication, session invalidation, audit events, API throttling, and security headers.
- Docker Compose and sample Nginx deployment configuration.
- Database backup/restore helpers, smoke-test script, synthetic demo examples, and GitHub Actions workflows.

### Version note
The application reports version `0.8.0` in its FastAPI metadata and health endpoints, and the UI displays `v0.8.0`. The matching Git tag for this source snapshot is therefore `v0.8.0`. Do not label this source snapshot `v1.0.0` unless the application version is deliberately updated and validated.

### Validation snapshot
- Automated tests: **48 passed** in the supplied project archive during the documentation refresh.
- Python compilation check: passed.
- Ruff lint: not run in the refresh environment because Ruff was not installed.
- Live PostgreSQL, Docker daemon, reverse proxy/TLS, GitHub App credentials, external AI providers, and production-host workflows were not validated as part of this documentation refresh.

### Important limitations
- AI output is advisory.
- Submitted code and generated tests are not executed.
- GitHub PR diff analysis is Python-focused.
- Non-Python source checks are heuristic.
- Repository scan schedules require an external runner.
- Production deployment requires environment-specific security, privacy, backup/restore, and operational validation.

See [`docs/production-readiness.md`](production-readiness.md) before deploying beyond local development or a controlled staging environment.
