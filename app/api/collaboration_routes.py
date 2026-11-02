from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_admin
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.repository import Repository
from app.models.team import Team, TeamMember, TeamRepository
from app.models.user import User
from app.services.audit_service import record_audit

router = APIRouter(tags=["team collaboration"])


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9 _.-]+$")
    description: str = Field(default="", max_length=500)


class TeamMemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class TeamRepositoryShare(BaseModel):
    repository_id: int = Field(ge=1)


def _team_payload(db: Session, team: Team) -> dict:
    members = db.scalars(select(TeamMember).where(TeamMember.team_id == team.id)).all()
    repositories = db.scalars(select(TeamRepository).where(TeamRepository.team_id == team.id)).all()
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "members": [
            {"user_id": m.user_id, "email": m.user.email, "full_name": m.user.full_name, "role": m.member_role}
            for m in members
        ],
        "repositories": [
            {"repository_id": link.repository_id, "owner": link.repository.owner, "name": link.repository.name}
            for link in repositories
        ],
        "created_at": team.created_at.isoformat(),
    }


@router.get("/admin/teams")
def all_teams(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    teams = db.scalars(select(Team).order_by(Team.created_at.desc())).all()
    return [_team_payload(db, team) for team in teams]


@router.post("/admin/teams", status_code=201)
def create_team(
    payload: TeamCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Team).where(Team.name == payload.name.strip()))
    if existing:
        raise HTTPException(status_code=409, detail="A team with this name already exists.")
    team = Team(name=payload.name.strip(), description=payload.description.strip(), created_by=admin.id)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=admin.id, member_role="team_admin"))
    db.commit()
    db.refresh(team)
    record_audit(db, admin.id, "team.created", "team", str(team.id), {"name": team.name})
    return _team_payload(db, team)


@router.post("/admin/teams/{team_id}/members", status_code=201)
def add_team_member(
    team_id: int,
    payload: TeamMemberCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user:
        raise HTTPException(status_code=404, detail="User account not found. Ask the user to register first.")
    existing = db.scalar(select(TeamMember).where(
        TeamMember.team_id == team_id, TeamMember.user_id == user.id
    ))
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this team.")
    db.add(TeamMember(team_id=team_id, user_id=user.id))
    db.commit()
    record_audit(db, admin.id, "team.member_added", "team", str(team_id), {"member_user_id": user.id})
    return _team_payload(db, team)


@router.delete("/admin/teams/{team_id}/members/{user_id}", status_code=204)
def remove_team_member(
    team_id: int,
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.scalar(select(TeamMember).where(
        TeamMember.team_id == team_id, TeamMember.user_id == user_id
    ))
    if not membership:
        raise HTTPException(status_code=404, detail="Team membership not found.")
    db.delete(membership)
    db.commit()
    record_audit(db, admin.id, "team.member_removed", "team", str(team_id), {"member_user_id": user_id})
    return None


@router.post("/admin/teams/{team_id}/repositories", status_code=201)
def share_repository_with_team(
    team_id: int,
    payload: TeamRepositoryShare,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not db.get(Team, team_id):
        raise HTTPException(status_code=404, detail="Team not found.")
    repo = db.get(Repository, payload.repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    existing = db.scalar(select(TeamRepository).where(
        TeamRepository.team_id == team_id, TeamRepository.repository_id == repo.id
    ))
    if existing:
        raise HTTPException(status_code=409, detail="Repository is already shared with this team.")
    db.add(TeamRepository(team_id=team_id, repository_id=repo.id))
    db.commit()
    record_audit(db, admin.id, "team.repository_shared", "team", str(team_id), {"repository_id": repo.id})
    return {"status": "shared", "team_id": team_id, "repository_id": repo.id}


@router.get("/teams")
def my_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    links = db.scalars(select(TeamMember).where(TeamMember.user_id == user.id)).all()
    return [_team_payload(db, link.team) for link in links]


@router.get("/repositories/shared")
def shared_repositories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team_ids = select(TeamMember.team_id).where(TeamMember.user_id == user.id)
    rows = db.scalars(
        select(Repository)
        .join(TeamRepository, TeamRepository.repository_id == Repository.id)
        .where(TeamRepository.team_id.in_(team_ids))
        .order_by(Repository.owner, Repository.name)
    ).all()
    # Deduplicate repositories shared through multiple teams.
    unique = {row.id: row for row in rows}
    return [
        {"id": row.id, "owner": row.owner, "name": row.name, "default_branch": row.default_branch,
         "url": f"https://github.com/{row.owner}/{row.name}"}
        for row in unique.values()
    ]


@router.get("/admin/users")
def admin_users(
    limit: int = Query(default=100, ge=1, le=500),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all()
    return [
        {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
         "is_active": u.is_active, "created_at": u.created_at.isoformat()}
        for u in users
    ]


@router.patch("/admin/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if role not in {"developer", "admin"}:
        raise HTTPException(status_code=400, detail="Role must be developer or admin.")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == admin.id and role != "admin":
        raise HTTPException(status_code=400, detail="Administrators cannot remove their own admin role.")
    target.role = role
    db.commit()
    record_audit(db, admin.id, "user.role_updated", "user", str(user_id), {"role": role})
    return {"id": target.id, "email": target.email, "role": target.role}


@router.get("/admin/audit-logs")
def audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        {"id": row.id, "user_id": row.user_id, "action": row.action,
         "resource_type": row.resource_type, "resource_id": row.resource_id,
         "details": row.details, "created_at": row.created_at.isoformat()}
        for row in rows
    ]
