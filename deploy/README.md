# Deployment notes

This project includes a Docker Compose PostgreSQL + FastAPI setup. The application container binds to `127.0.0.1:8000`; expose it through a trusted HTTPS reverse proxy rather than directly to the public internet.

## Before deployment

1. Provision a supported Linux host and Docker Engine + Compose plugin.
2. Create `.env` from `.env.production.example` and set unique secrets. Do not commit it.
3. Set `CORS_ORIGINS` to the exact public origin (scheme + hostname), and `TRUSTED_HOSTS` to the expected hostnames only.
4. Set `POSTGRES_PASSWORD` to a long random value and `JWT_SECRET` to at least 32 random bytes. Keep both in a secret manager where available.
5. Configure DNS and obtain a valid TLS certificate.
6. Review GitHub App permissions and AI-provider data handling with the organisation before enabling integrations.
7. Back up any existing database before upgrading. Migrations run at application startup.

## Start

```bash
cp .env.production.example .env
# Edit .env securely, then:
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 codeguard
python scripts/smoke_test.py https://codeguard.example.com
```

`docker compose config` may display interpolated secrets; do not paste its output into tickets or public logs. `scripts/smoke_test.py` checks public liveness/readiness and the dashboard response; it does not test authentication, GitHub credentials, AI providers or application security comprehensively.

## Reverse proxy

Use `deploy/nginx.conf` as a starting point for a host-level Nginx reverse proxy. Replace the example hostname and certificate paths. The sample assumes TLS is terminated at Nginx and that the app is reachable only on loopback. Review forwarded-header trust, firewall rules and certificate renewal for your environment.

## Database backup and restore

Create a compressed logical backup:

```bash
./scripts/backup_postgres.sh
```

Restore is destructive to the target database and requires an explicit confirmation string:

```bash
./scripts/restore_postgres.sh backups/codeguard_YYYYMMDD_HHMMSS.dump
```

The scripts use `docker compose exec` and expect the Compose service to be named `db`. Store backups encrypted, restrict access, and test restores periodically. A backup is not proven until a restore has been verified.

## Release / rollback

- Record the deployed Git commit and image digest.
- Take and verify a backup before deployment.
- Review Alembic migration output in application logs.
- Run the smoke test and a controlled sign-in/review flow.
- If rollback is needed, deploy the previous image only after checking schema compatibility. Do not assume a database downgrade is safe; the project intentionally retains user data in downgrade operations.
