from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db.database import engine
from app.main import app

client = TestClient(app)


def create_account():
    email = f"phase6-{uuid4().hex}@example.com"
    password = "A-strong-phase6-password-123"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Phase Six User",
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return email, password, response.json()["access_token"]


def test_migration_adds_token_version_column():
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert "token_version" in columns


def test_logout_revokes_existing_access_token():
    _, _, token = create_account()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_password_change_revokes_old_token_and_new_password_works():
    email, password, token = create_account()
    headers = {"Authorization": f"Bearer {token}"}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": password,
            "new_password": "A-different-strong-password-456",
        },
    )
    assert changed.status_code == 200, changed.text
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "A-different-strong-password-456",
        },
    )
    assert login.status_code == 200


def test_security_headers_and_readiness_endpoint():
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers.get("x-request-id")


def test_production_configuration_rejects_placeholder_secret(monkeypatch):
    from app.core.config import validate_runtime_config

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "replace-with-a-long-random-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/db")
    monkeypatch.setenv("CORS_ORIGINS", "https://codeguard.example.com")
    monkeypatch.setenv("ENABLE_HSTS", "true")
    try:
        validate_runtime_config()
    except RuntimeError as exc:
        assert "JWT_SECRET" in str(exc)
    else:
        raise AssertionError("Placeholder secret should be rejected in production.")


def test_request_size_limit_rejects_oversized_declared_body():
    response = client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={"Content-Length": "1000001", "Content-Type": "application/json"},
    )
    assert response.status_code == 413
