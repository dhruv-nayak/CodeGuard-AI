import os


def validate_runtime_config() -> None:
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    if environment not in {"development", "test", "staging", "production"}:
        raise RuntimeError("ENVIRONMENT must be development, test, staging or production.")
    if environment == "production":
        secret = os.getenv("JWT_SECRET", "")
        invalid_secret = (
            len(secret.encode("utf-8")) < 32
            or "replace-with" in secret.lower()
            or "dev-only" in secret.lower()
        )
        if invalid_secret:
            raise RuntimeError(
                "Production requires a JWT_SECRET containing at least 32 non-placeholder bytes."
            )
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url.startswith("sqlite") or not database_url:
            raise RuntimeError(
                "Production requires an explicitly configured PostgreSQL DATABASE_URL."
            )
        origins = os.getenv("CORS_ORIGINS", "").strip()
        if not origins or origins == "*":
            raise RuntimeError("Production CORS_ORIGINS must explicitly list trusted origins.")
        trusted_hosts = os.getenv("TRUSTED_HOSTS", "").strip()
        if not trusted_hosts or "*" in trusted_hosts:
            raise RuntimeError("Production TRUSTED_HOSTS must explicitly list allowed hostnames.")
        db_password = os.getenv("POSTGRES_PASSWORD", "")
        invalid_db_password = (
            len(db_password) < 20
            or "change-this" in db_password.lower()
            or "replace-with" in db_password.lower()
        )
        if invalid_db_password:
            raise RuntimeError(
                "Production requires a strong POSTGRES_PASSWORD of at least 20 characters."
            )
        if os.getenv("ENABLE_HSTS", "true").lower() not in {"true", "1", "yes"}:
            raise RuntimeError(
                "Production must enable HSTS and terminate HTTPS at the trusted proxy."
            )


def csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]
