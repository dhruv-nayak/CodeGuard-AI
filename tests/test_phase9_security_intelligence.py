from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.api import github_routes
from app.services.repository_intelligence import make_sbom

client=TestClient(app)

def _account():
    email=f"phase9-{uuid4().hex}@example.com"
    response=client.post("/api/v1/auth/register",json={"email":email,"full_name":"Phase Nine","password":"A-strong-phase9-password-123"})
    assert response.status_code==201,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}

def test_dashboard_remediation_alerts_and_exports(monkeypatch):
    async def fake_scan(owner,repo,token):
        return {"repository":f"{owner}/{repo}","files_reviewed":1,"files_skipped":0,
                "findings":[{"rule_id":"PY-SEC-001","title":"Unsafe execution","severity":"high","file":"app.py","line":4,"message":"Potential unsafe execution"}],
                "findings_count":1,"dependencies":[],"dependency_count":0,"dependency_vulnerabilities":[],
                "vulnerable_dependency_count":0,"osv_status":"fixture","sbom":make_sbom(owner,repo,"main",[]),"limitations":[]}
    monkeypatch.setattr(github_routes,"scan_github_repository",fake_scan)
    headers=_account()
    scan=client.post("/api/v1/github/repositories/scan",headers=headers,json={"owner":"sample","repo":"project","github_token":"test-token"})
    assert scan.status_code==200,scan.text
    review_id=scan.json()["review_id"]
    dashboard=client.get("/api/v1/security/dashboard",headers=headers).json()
    assert dashboard["scans"]==1 and dashboard["risk_score"]<100
    findings=client.get("/api/v1/security/remediations",headers=headers).json()
    assert len(findings)==1 and findings[0]["status"]=="open"
    fp=findings[0]["fingerprint"]
    update=client.patch(f"/api/v1/security/remediations/{review_id}/{fp}",headers=headers,json={"status":"resolved","note":"Fixed in patch"})
    assert update.status_code==200 and update.json()["status"]=="resolved"
    alerts=client.get("/api/v1/security/alerts",headers=headers).json()
    assert alerts["count"]==0
    for fmt,content_type in [("csv","text/csv"),("xlsx","spreadsheetml"),("pdf","application/pdf")]:
        exported=client.get(f"/api/v1/security/reports/export?format={fmt}",headers=headers)
        assert exported.status_code==200 and content_type in exported.headers["content-type"]

def test_schedule_create_list_and_team_access():
    headers=_account()
    repo=client.post("/api/v1/repositories",headers=headers,json={"owner":"sample","name":"scheduled","default_branch":"main"})
    assert repo.status_code==201,repo.text
    schedule=client.post("/api/v1/security/schedules",headers=headers,json={"repository_id":repo.json()["id"],"cadence":"daily"})
    assert schedule.status_code==201,schedule.text
    assert "external scheduler" in schedule.json()["execution"].lower()
    listed=client.get("/api/v1/security/schedules",headers=headers)
    assert listed.status_code==200 and len(listed.json())==1
    deleted=client.delete(f"/api/v1/security/schedules/{schedule.json()['id']}",headers=headers)
    assert deleted.status_code==204
    denied=client.get("/api/v1/security/teams/99999/dashboard",headers=headers)
    assert denied.status_code==403
