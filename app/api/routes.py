import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.repository import Repository
from app.models.review import Review
from app.models.user import User
from app.schemas.auth import ReviewHistoryItem, RepositoryCreate, RepositoryResponse
from app.schemas.github import GitHubReviewRequest, GitHubReviewResponse
from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.audit_service import record_audit
from app.services.github_app_service import create_installation_token
from app.services.github_service import review_pull_request
from app.services.history_service import get_review, list_reviews, save_review
from app.services.review_service import review_code

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "CodeGuard AI", "version": "0.8.0"}


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    payload: ReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = await review_code(payload)
        save_review(
            db, user, result.review_id, result.model_dump(mode="json"),
            review_type="code", filename=result.filename,
        )
        record_audit(db, user.id, "code.review_created", "review", result.review_id,
                     {"filename": result.filename})
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/github/pull-requests/review", response_model=GitHubReviewResponse)
async def review_github_pull_request(
    payload: GitHubReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        token = payload.github_token
        if not token and payload.installation_id:
            token_data = await create_installation_token(payload.installation_id)
            token = token_data["token"]
        result = await review_pull_request(
            owner=payload.owner, repo=payload.repo, pull_number=payload.pull_number,
            token=token, ai_provider=payload.ai_provider,
        )
        result_data = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
        review_id = str(uuid4())
        result_data["review_id"] = review_id
        save_review(
            db, user, review_id, result_data, review_type="github_pr",
            filename=f"PR #{result_data['pull_number']}", repository=result_data["repository"],
        )
        record_audit(db, user.id, "github.pull_request_reviewed", "review", review_id,
                     {"repository": result_data["repository"], "pull_number": result_data["pull_number"]})
        return result_data
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="GitHub review could not be completed. Check repository access and try again.",
        ) from exc


@router.get("/reviews/history", response_model=list[ReviewHistoryItem])
def review_history(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_reviews(db, user, limit)
    return [
        ReviewHistoryItem(
            review_id=row.review_id, review_type=row.review_type, filename=row.filename,
            repository=row.repository, score=row.score, summary=row.summary,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.get("/reviews/history/{review_id}")
def review_history_detail(
    review_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_review(db, user, review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found.")
    return row.result_json


@router.get("/repositories", response_model=list[RepositoryResponse])
def repositories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Repository).where(Repository.user_id == user.id).order_by(Repository.created_at.desc())
    )
    return [
        RepositoryResponse(
            id=row.id, owner=row.owner, name=row.name, default_branch=row.default_branch,
            created_at=row.created_at.isoformat(),
            url=f"https://github.com/{row.owner}/{row.name}",
        )
        for row in rows
    ]


@router.post("/repositories", response_model=RepositoryResponse, status_code=201)
def add_repository(
    payload: RepositoryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner, name = payload.owner.strip(), payload.name.strip()
    existing = db.scalar(select(Repository).where(
        Repository.user_id == user.id,
        Repository.owner == owner,
        Repository.name == name,
    ))
    if existing:
        raise HTTPException(status_code=409, detail="This repository is already registered.")
    row = Repository(
        user_id=user.id, owner=owner, name=name, default_branch=payload.default_branch.strip()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(db, user.id, "repository.created", "repository", str(row.id),
                 {"owner": owner, "name": name})
    return RepositoryResponse(
        id=row.id, owner=row.owner, name=row.name, default_branch=row.default_branch,
        created_at=row.created_at.isoformat(), url=f"https://github.com/{row.owner}/{row.name}",
    )


@router.delete("/repositories/{repository_id}", status_code=204)
def remove_repository(
    repository_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(Repository).where(
        Repository.id == repository_id, Repository.user_id == user.id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Repository not found.")
    db.delete(row)
    db.commit()
    record_audit(db, user.id, "repository.deleted", "repository", str(repository_id))
    return Response(status_code=204)


@router.get("/reviews/history/{review_id}/tests")
def download_generated_tests(
    review_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_review(db, user, review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found.")
    ai_review = (row.result_json or {}).get("ai_review") or {}
    tests = ai_review.get("generated_tests")
    if not tests or not tests.strip():
        raise HTTPException(status_code=404, detail="No generated test module is available for this review.")
    base_name = re.sub(r"[^A-Za-z0-9_-]", "_", row.filename.rsplit(".", 1)[0]) or "review"
    language = str((row.result_json or {}).get("language", "python")).lower()
    extension = {"python": "py", "javascript": "js", "typescript": "ts", "java": "java", "php": "php", "sql": "sql", "html": "html"}.get(language, "txt")
    media_type = "text/plain" if extension in {"sql", "html"} else "text/x-python" if extension == "py" else "text/plain"
    return Response(
        content=tests,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{base_name}_generated_tests.{extension}"'},
    )


@router.get("/analytics/overview")
def analytics_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregate metrics for the authenticated user's saved reviews only."""
    rows = list(db.scalars(select(Review).where(Review.user_id == user.id)))
    severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    languages: dict[str, int] = {}
    rules: dict[str, int] = {}
    scores: list[int] = []
    for row in rows:
        result = row.result_json or {}
        language = str(result.get("language") or "unknown").lower()
        languages[language] = languages.get(language, 0) + 1
        if isinstance(row.score, int):
            scores.append(row.score)
        for finding in result.get("findings", []):
            level = str(finding.get("severity", "info")).lower()
            if level in severity:
                severity[level] += 1
            rule_id = str(finding.get("rule_id") or "unknown")
            rules[rule_id] = rules.get(rule_id, 0) + 1
    top_rules = sorted(rules.items(), key=lambda item: (-item[1], item[0]))[:10]
    return {
        "total_reviews": len(rows),
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "severity_distribution": severity,
        "language_distribution": languages,
        "top_rules": [{"rule_id": key, "count": value} for key, value in top_rules],
        "scope": "Authenticated user's saved reviews only",
    }


@router.get("/reviews/history/{review_id}/sbom")
def download_review_sbom(
    review_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the CycloneDX JSON SBOM from an owned repository scan."""
    row = get_review(db, user, review_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found.")
    if row.review_type != "repository_scan":
        raise HTTPException(status_code=400, detail="This review does not contain a repository SBOM.")
    sbom = (row.result_json or {}).get("sbom")
    if not isinstance(sbom, dict):
        raise HTTPException(status_code=404, detail="SBOM is not available for this scan.")
    owner_repo = re.sub(r"[^A-Za-z0-9_.-]", "_", row.repository or "repository")
    return Response(
        content=__import__("json").dumps(sbom, indent=2),
        media_type="application/vnd.cyclonedx+json",
        headers={"Content-Disposition": f'attachment; filename="{owner_repo}.cdx.json"'},
    )
