from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.database import init_db
from app.main import app

init_db()

client = TestClient(app)


def create_user():
    email = f"test-{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Test Developer",
            "password": "A-strong-test-password-123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_reviews_require_authentication():
    response = client.post(
        "/api/v1/reviews", json={"filename": "sample.py", "language": "python", "code": "x = 1"}
    )
    assert response.status_code == 401


def test_review_detects_bare_except_and_saves_history():
    token = create_user()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={
            "filename": "sample.py",
            "language": "python",
            "code": "def f():\n    try:\n        return 1\n    except:\n        return 0\n",
        },
    )
    assert response.status_code == 200, response.text
    review = response.json()
    assert any(x["rule_id"] == "PY-QUAL-001" for x in review["findings"])
    history = client.get("/api/v1/reviews/history", headers=headers)
    assert history.status_code == 200
    assert any(x["review_id"] == review["review_id"] for x in history.json())


def test_review_rejects_empty_code():
    token = create_user()
    response = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"filename": "empty.py", "language": "python", "code": ""},
    )
    assert response.status_code == 422


def test_users_cannot_read_other_users_review():
    first_token = create_user()
    headers = {"Authorization": f"Bearer {first_token}"}
    response = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"filename": "private.py", "language": "python", "code": "value = 42"},
    )
    review_id = response.json()["review_id"]
    other_token = create_user()
    denied = client.get(
        f"/api/v1/reviews/history/{review_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert denied.status_code == 404


def test_login_returns_bearer_token():
    email = f"login-{uuid4().hex}@example.com"
    password = "A-strong-test-password-123"
    created = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Login User", "password": password},
    )
    assert created.status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_developer_cannot_access_admin_route():
    token = create_user()
    response = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_repository_registry_is_user_scoped():
    first_token = create_user()
    first_headers = {"Authorization": f"Bearer {first_token}"}
    created = client.post(
        "/api/v1/repositories",
        headers=first_headers,
        json={"owner": "octocat", "name": "hello-world", "default_branch": "main"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["url"] == "https://github.com/octocat/hello-world"
    assert len(client.get("/api/v1/repositories", headers=first_headers).json()) == 1

    second_token = create_user()
    second_headers = {"Authorization": f"Bearer {second_token}"}
    assert client.get("/api/v1/repositories", headers=second_headers).json() == []
    assert (
        client.delete(
            f"/api/v1/repositories/{created.json()['id']}", headers=second_headers
        ).status_code
        == 404
    )


def test_generated_test_download_requires_existing_review():
    token = create_user()
    response = client.get(
        "/api/v1/reviews/history/not-a-real-review/tests",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def create_admin():
    from app.core.security import create_access_token, hash_password
    from app.db.database import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        email = f"admin-{uuid4().hex}@example.com"
        user = User(
            email=email,
            full_name="Test Admin",
            password_hash=hash_password("A-strong-admin-password-123"),
            role="admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id, user.role)
        return token, user.id


def test_admin_can_create_team_and_add_registered_member():
    admin_token, _ = create_admin()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_email = f"member-{uuid4().hex}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "full_name": "Team Member",
            "password": "A-strong-member-password-123",
        },
    )
    assert register.status_code == 201

    team_response = client.post(
        "/api/v1/admin/teams",
        headers=admin_headers,
        json={"name": f"Platform Team {uuid4().hex[:6]}", "description": "Shared code review team"},
    )
    assert team_response.status_code == 201, team_response.text
    team = team_response.json()

    add_response = client.post(
        f"/api/v1/admin/teams/{team['id']}/members",
        headers=admin_headers,
        json={"email": member_email},
    )
    assert add_response.status_code == 201, add_response.text
    member_token = register.json()["access_token"]
    my_teams = client.get("/api/v1/teams", headers={"Authorization": f"Bearer {member_token}"})
    assert my_teams.status_code == 200
    assert any(x["id"] == team["id"] for x in my_teams.json())


def test_developer_cannot_create_team_or_view_admin_audit():
    token = create_user()
    headers = {"Authorization": f"Bearer {token}"}
    denied = client.post("/api/v1/admin/teams", headers=headers, json={"name": "Nope"})
    assert denied.status_code == 403
    logs = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert logs.status_code == 403


def test_github_app_status_endpoint_requires_authentication():
    response = client.get("/api/v1/github/app/status")
    assert response.status_code == 401


def test_github_publish_requires_explicit_confirmation():
    token = create_user()
    response = client.post(
        "/api/v1/github/reviews/not-real/publish-comments",
        headers={"Authorization": f"Bearer {token}"},
        json={"github_token": "not-a-real-token", "confirmation": "yes"},
    )
    assert response.status_code == 422


def test_github_comment_draft_is_private_to_review_owner():
    from app.db.database import SessionLocal
    from app.models.user import User
    from app.services.history_service import save_review

    token = create_user()
    owner = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    review_id = str(uuid4())
    result = {
        "repository": "octocat/hello-world",
        "pull_number": 7,
        "head_sha": "abc123",
        "file_results": [
            {
                "filename": "sample.py",
                "findings": [
                    {
                        "line": 3,
                        "severity": "high",
                        "title": "Unsafe operation",
                        "message": "Potentially unsafe call.",
                        "recommendation": "Use a safer API.",
                    }
                ],
            }
        ],
    }
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == owner["id"]).one()
        save_review(
            db, user, review_id, result, review_type="github_pr", repository="octocat/hello-world"
        )
    headers = {"Authorization": f"Bearer {token}"}
    draft = client.get(f"/api/v1/github/reviews/{review_id}/comment-draft", headers=headers)
    assert draft.status_code == 200
    assert draft.json()["comment_count"] == 1
    assert draft.json()["comments"][0]["line"] == 3
    other = create_user()
    hidden = client.get(
        f"/api/v1/github/reviews/{review_id}/comment-draft",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert hidden.status_code == 404


def test_team_repository_share_is_visible_to_team_member():
    admin_token, _ = create_admin()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    repo_response = client.post(
        "/api/v1/repositories",
        headers=admin_headers,
        json={"owner": "octocat", "name": f"shared-{uuid4().hex[:6]}", "default_branch": "main"},
    )
    assert repo_response.status_code == 201, repo_response.text
    repository_id = repo_response.json()["id"]

    team_response = client.post(
        "/api/v1/admin/teams",
        headers=admin_headers,
        json={"name": f"Shared Team {uuid4().hex[:6]}"},
    )
    assert team_response.status_code == 201, team_response.text
    team_id = team_response.json()["id"]

    member_email = f"shared-{uuid4().hex}@example.com"
    member = client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "full_name": "Shared Member",
            "password": "A-strong-shared-password-123",
        },
    )
    assert member.status_code == 201
    add = client.post(
        f"/api/v1/admin/teams/{team_id}/members",
        headers=admin_headers,
        json={"email": member_email},
    )
    assert add.status_code == 201
    share = client.post(
        f"/api/v1/admin/teams/{team_id}/repositories",
        headers=admin_headers,
        json={"repository_id": repository_id},
    )
    assert share.status_code == 201, share.text

    shared = client.get(
        "/api/v1/repositories/shared",
        headers={"Authorization": f"Bearer {member.json()['access_token']}"},
    )
    assert shared.status_code == 200
    assert any(item["id"] == repository_id for item in shared.json())


def test_github_pr_review_response_persists_review_id():
    from unittest.mock import AsyncMock, patch

    token = create_user()
    mocked = {
        "repository": "octocat/hello-world",
        "pull_number": 4,
        "pull_title": "Test PR",
        "pull_url": "https://github.com/octocat/hello-world/pull/4",
        "head_sha": "deadbeef",
        "files_reviewed": 1,
        "files_skipped": 0,
        "findings_count": 0,
        "file_results": [],
        "ai_summary": None,
        "ai_provider": None,
        "limitations": [],
    }
    with patch("app.api.routes.review_pull_request", new_callable=AsyncMock, return_value=mocked):
        response = client.post(
            "/api/v1/github/pull-requests/review",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "owner": "octocat",
                "repo": "hello-world",
                "pull_number": 4,
                "github_token": "temporary-test-token",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["review_id"]
    history = client.get("/api/v1/reviews/history", headers={"Authorization": f"Bearer {token}"})
    assert any(row["review_type"] == "github_pr" for row in history.json())
