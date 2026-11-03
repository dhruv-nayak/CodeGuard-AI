from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_multilanguage_review_and_user_analytics():
    email = f"phase7-{uuid4().hex}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Phase Seven User",
            "password": "A-strong-phase7-password-123",
        },
    )
    assert registered.status_code == 201, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    review = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={
            "filename": "app.js",
            "language": "javascript",
            "code": "eval(userInput); element.innerHTML = userInput;",
            "ai_provider": "auto",
        },
    )
    assert review.status_code == 200, review.text
    data = review.json()
    assert data["language"] == "javascript"
    assert any(item["rule_id"] == "JS-SEC-001" for item in data["findings"])
    analytics = client.get("/api/v1/analytics/overview", headers=headers)
    assert analytics.status_code == 200
    metrics = analytics.json()
    assert metrics["total_reviews"] == 1
    assert metrics["language_distribution"] == {"javascript": 1}
    assert metrics["severity_distribution"]["high"] >= 1
