from app.services.repository_intelligence import make_sbom, parse_manifests


def test_parse_pinned_python_and_npm_dependencies():
    deps = parse_manifests(
        {
            "requirements.txt": "fastapi==0.115.0\n# comment\nrequests>=2.0\nunpinned-package\n",
            "web/package-lock.json": (
                '{"lockfileVersion":3,"packages":{"":{"name":"demo"},'
                '"node_modules/lodash":{"version":"4.17.21"},'
                '"node_modules/@scope/pkg":{"version":"1.2.3"}}}'
            ),
        }
    )
    values = {(d.ecosystem, d.name, d.version) for d in deps}
    assert ("PyPI", "fastapi", "0.115.0") in values
    assert ("npm", "lodash", "4.17.21") in values
    assert ("npm", "@scope/pkg", "1.2.3") in values
    assert not any(d.name == "requests" for d in deps)


def test_parse_composer_and_maven_lockfiles():
    deps = parse_manifests(
        {
            "composer.lock": '{"packages":[{"name":"vendor/library","version":"v2.4.1"}]}',
            "pom.xml": (
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<dependencies><dependency><groupId>org.example</groupId>"
                "<artifactId>demo</artifactId><version>1.4.0</version>"
                "</dependency></dependencies></project>"
            ),
        }
    )
    values = {(d.ecosystem, d.name, d.version) for d in deps}
    assert ("Packagist", "vendor/library", "2.4.1") in values
    assert ("Maven", "org.example:demo", "1.4.0") in values


def test_sbom_uses_cyclonedx_15_and_package_urls():
    deps = parse_manifests({"requirements.txt": "urllib3==2.2.2\n"})
    sbom = make_sbom("owner", "repo", "main", deps)
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["components"][0]["purl"] == "pkg:pypi/urllib3@2.2.2"


def test_repository_scan_api_saves_report_and_downloads_sbom(monkeypatch):
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from app.api import github_routes
    from app.main import app

    async def fake_scan(owner, repo, token):
        deps = parse_manifests({"requirements.txt": "urllib3==2.2.2\n"})
        return {
            "repository": f"{owner}/{repo}",
            "files_reviewed": 1,
            "files_skipped": 0,
            "findings": [],
            "findings_count": 0,
            "dependencies": [d.__dict__ for d in deps],
            "dependency_count": 1,
            "dependency_vulnerabilities": [],
            "vulnerable_dependency_count": 0,
            "osv_status": "fixture",
            "sbom": make_sbom(owner, repo, "main", deps),
            "limitations": [],
        }

    async def fake_token(installation_id):
        return {"token": "fixture-token"}

    monkeypatch.setattr(github_routes, "scan_github_repository", fake_scan)
    monkeypatch.setattr(github_routes, "create_installation_token", fake_token)
    client = TestClient(app)
    email = f"phase8-{uuid4().hex}@example.com"
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Phase Eight",
            "password": "A-strong-phase8-password-123",
        },
    )
    assert registration.status_code == 201, registration.text
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    scan = client.post(
        "/api/v1/github/repositories/scan",
        headers=headers,
        json={
            "owner": "example",
            "repo": "demo",
            "github_token": "fixture-token",
        },
    )
    assert scan.status_code == 200, scan.text
    review_id = scan.json()["review_id"]
    sbom = client.get(f"/api/v1/reviews/history/{review_id}/sbom", headers=headers)
    assert sbom.status_code == 200
    assert sbom.json()["bomFormat"] == "CycloneDX"
    assert sbom.headers["content-type"].startswith("application/vnd.cyclonedx+json")
