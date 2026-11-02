from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_accessible_navigation_and_phase10_version():
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="#main"' in response.text
    assert 'aria-label="Main navigation"' in response.text
    assert "v0.8.0" in response.text


def test_dashboard_assets_are_served():
    css = client.get("/styles.css")
    js = client.get("/app.js")
    assert css.status_code == 200 and ".skip-link" in css.text
    assert js.status_code == 200 and "codeguard_access_token" in js.text


def test_launch_assets_and_demo_samples_exist():
    assert (ROOT / ".env.production.example").is_file()
    assert (ROOT / "deploy" / "nginx.conf").is_file()
    assert (ROOT / "docs" / "launch-checklist.md").is_file()
    assert (ROOT / "scripts" / "smoke_test.py").is_file()
    assert (ROOT / "demo" / "samples" / "python_example.py").is_file()
    assert (ROOT / "demo" / "samples" / "javascript_example.js").is_file()
