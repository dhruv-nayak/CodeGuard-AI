from urllib.parse import quote
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.github import PublishCommentsRequest, RepositoryScanRequest
from app.services.audit_service import record_audit
from app.services.github_app_service import create_installation_token, github_app_configured
from app.services.history_service import get_review, save_review
from app.services.repository_intelligence import scan_github_repository
from uuid import uuid4

router = APIRouter(prefix="/github", tags=["GitHub integration"])
GITHUB_API = "https://api.github.com"


async def _get_token(payload) -> str:
    if payload.github_token:
        return payload.github_token
    token_data = await create_installation_token(payload.installation_id)
    return token_data["token"]


@router.get("/app/status")
def app_status(user: User = Depends(get_current_user)):
    return {
        "configured": github_app_configured(),
        "authentication": "GitHub App installation tokens" if github_app_configured() else "Personal access token",
        "note": "Installation tokens are short-lived and are not stored by CodeGuard."
    }


@router.get("/reviews/{review_id}/comment-draft")
def draft_review_comments(
    review_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_review(db, user, review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found.")
    if row.review_type != "github_pr":
        raise HTTPException(status_code=400, detail="This review is not a GitHub pull request review.")
    result = row.result_json or {}
    comments = []
    for file_result in result.get("file_results", []):
        path = file_result.get("filename")
        for finding in file_result.get("findings", []):
            line = finding.get("line")
            if not isinstance(line, int) or line < 1:
                continue
            title = str(finding.get("title", "Code review finding"))[:180]
            severity = str(finding.get("severity", "info"))[:20]
            message = str(finding.get("message", ""))[:1200]
            recommendation = str(finding.get("recommendation", ""))[:1200]
            body = f"**{severity.upper()} – {title}**\n\n{message}\n\n**Recommendation:** {recommendation}"
            comments.append({"path": path, "line": line, "side": "RIGHT", "body": body})
    return {
        "review_id": row.review_id,
        "repository": result.get("repository", row.repository),
        "pull_number": result.get("pull_number"),
        "head_sha": result.get("head_sha"),
        "comment_count": len(comments),
        "comments": comments,
        "publishing_requires_explicit_confirmation": "PUBLISH_COMMENTS",
        "note": "Review comments are drafts. Confirm every comment before publishing. CodeGuard will publish a COMMENT review, never APPROVE or REQUEST_CHANGES."
    }


@router.post("/reviews/{review_id}/publish-comments")
async def publish_review_comments(
    review_id: str,
    payload: PublishCommentsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_review(db, user, review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found.")
    if row.review_type != "github_pr":
        raise HTTPException(status_code=400, detail="This review is not a GitHub pull request review.")
    result = row.result_json or {}
    repository = result.get("repository", "")
    pull_number = result.get("pull_number")
    head_sha = result.get("head_sha")
    if not repository or not isinstance(pull_number, int) or not head_sha:
        raise HTTPException(status_code=400, detail="Saved pull request metadata is incomplete.")

    draft_comments = []
    for file_result in result.get("file_results", []):
        path = file_result.get("filename")
        for finding in file_result.get("findings", []):
            line = finding.get("line")
            if not path or not isinstance(line, int) or line < 1:
                continue
            title = str(finding.get("title", "Code review finding"))[:180]
            severity = str(finding.get("severity", "info"))[:20]
            message = str(finding.get("message", ""))[:1200]
            recommendation = str(finding.get("recommendation", ""))[:1200]
            body = f"**{severity.upper()} – {title}**\n\n{message}\n\n**Recommendation:** {recommendation}"
            draft_comments.append({"path": path, "line": line, "side": "RIGHT", "body": body})
    if not draft_comments:
        raise HTTPException(status_code=400, detail="There are no line-specific findings to publish.")
    try:
        token = await _get_token(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    owner, repo = repository.split("/", 1)
    url = f"{GITHUB_API}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls/{pull_number}/reviews"
    request_body = {
        "commit_id": head_sha,
        "body": f"CodeGuard AI review – {len(draft_comments)} finding(s). Please review the suggestions before merging.",
        "event": "COMMENT",
        "comments": draft_comments,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=request_body,
        )
    if response.status_code in (401, 403):
        raise HTTPException(status_code=403, detail="GitHub rejected comment publishing. Check Pull requests: write permission.")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub pull request was not found or is not accessible.")
    if response.status_code == 422:
        raise HTTPException(status_code=422, detail="GitHub could not place one or more comments on the current diff. Re-run the review against the latest pull request.")
    response.raise_for_status()
    published = response.json()
    record_audit(
        db, user.id, "github.review_comments_published", "review", review_id,
        {"repository": repository, "pull_number": pull_number, "comment_count": len(draft_comments),
         "github_review_id": published.get("id")},
    )
    return {
        "status": "published",
        "event": "COMMENT",
        "comment_count": len(draft_comments),
        "github_review_url": published.get("html_url"),
        "message": "Comments published. CodeGuard did not approve or request changes on this pull request."
    }


@router.post("/repositories/scan")
async def scan_repository(
    payload: RepositoryScanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only repository scan, dependency audit and CycloneDX SBOM generation."""
    try:
        token = await _get_token(payload)
        result = await scan_github_repository(payload.owner, payload.repo, token)
        review_id = str(uuid4())
        result["review_id"] = review_id
        result["summary"] = (
            f"Repository scan reviewed {result['files_reviewed']} source file(s), "
            f"found {result['findings_count']} static signal(s), and identified "
            f"{result['dependency_count']} pinned dependencies."
        )
        save_review(
            db, user, review_id, result, review_type="repository_scan",
            filename=f"{payload.owner}/{payload.repo}", repository=f"{payload.owner}/{payload.repo}",
        )
        record_audit(db, user.id, "github.repository_scanned", "repository", f"{payload.owner}/{payload.repo}",
                     {"review_id": review_id, "files_reviewed": result["files_reviewed"],
                      "dependency_count": result["dependency_count"]})
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Repository scan failed. Check GitHub access and retry.") from exc
