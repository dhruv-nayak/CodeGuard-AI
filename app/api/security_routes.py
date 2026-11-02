"""Phase 9 security intelligence, remediation and reporting endpoints."""
from __future__ import annotations
import csv, hashlib, io, json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.review import Review
from app.models.remediation import FindingRemediation, RepositorySchedule
from app.models.repository import Repository
from app.models.team import TeamMember, TeamRepository
from app.services.audit_service import record_audit

router = APIRouter(prefix="/security", tags=["Security intelligence"])
STATUSES = {"open", "in_progress", "resolved", "accepted_risk", "false_positive"}


def _findings(row: Review):
    result = row.result_json or {}
    values = []
    for finding in result.get("findings", []):
        item = dict(finding)
        item.setdefault("file", "")
        values.append(item)
    for vuln in result.get("dependency_vulnerabilities", []):
        values.append({"rule_id": vuln.get("id", "DEPENDENCY-VULN"), "title": vuln.get("id", "Dependency vulnerability"),
                       "message": vuln.get("summary", "Known dependency advisory"), "severity": vuln.get("severity", "high"),
                       "file": "dependency:" + str(vuln.get("dependency", "")), "version": vuln.get("version"),
                       "recommendation": "Upgrade to a fixed version after reviewing the upstream advisory."})
    return values


def _fingerprint(finding: dict) -> str:
    stable = {k: finding.get(k) for k in ("rule_id", "title", "file", "line", "message")}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()


def _risk_score(rows: list[Review]) -> int:
    weights = {"critical": 15, "high": 8, "medium": 4, "low": 1, "info": 0}
    total = sum(weights.get(str(f.get("severity", "info")).lower(), 0) for row in rows for f in _findings(row))
    return max(0, min(100, 100 - total))


def _summary(rows: list[Review]):
    severity = Counter(); repos = Counter(); days = defaultdict(Counter); scores=[]
    for row in rows:
        repos[row.repository or row.filename or "unknown"] += 1
        if row.score is not None: scores.append(row.score)
        date = row.created_at.date().isoformat() if row.created_at else "unknown"
        for f in _findings(row):
            sev = str(f.get("severity", "info")).lower()
            severity[sev] += 1; days[date][sev] += 1
    return {"scans":len(rows), "repositories":len(repos), "average_quality_score":round(sum(scores)/len(scores),1) if scores else None,
            "risk_score":_risk_score(rows), "severity_distribution":dict(severity),
            "repository_scan_counts":[{"repository":k,"scans":v} for k,v in repos.most_common(20)],
            "daily_trend":[{"date":d,"findings":sum(v.values()),"critical":v.get("critical",0),"high":v.get("high",0)} for d,v in sorted(days.items())]}


@router.get("/dashboard")
def security_dashboard(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    rows=list(db.scalars(select(Review).where(Review.user_id==user.id, Review.review_type=="repository_scan").order_by(Review.created_at.desc()).limit(500)))
    result=_summary(rows)
    remediations=list(db.scalars(select(FindingRemediation).where(FindingRemediation.user_id==user.id)))
    result["remediation_distribution"] = dict(Counter(r.status for r in remediations))
    result["scope"]="Your repository scans only"
    return result


@router.get("/teams/{team_id}/dashboard")
def team_security_dashboard(team_id:int, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    member=db.scalar(select(TeamMember).where(TeamMember.team_id==team_id, TeamMember.user_id==user.id))
    if not member and user.role != "admin": raise HTTPException(403,"Team membership required.")
    team_repos=list(db.scalars(select(Repository).join(TeamRepository, TeamRepository.repository_id==Repository.id).where(TeamRepository.team_id==team_id)))
    names={f"{r.owner}/{r.name}" for r in team_repos}; owner_ids={r.user_id for r in team_repos}
    if not names: return {**_summary([]),"team_id":team_id,"scope":"Repositories shared with this team"}
    rows=list(db.scalars(select(Review).where(Review.review_type=="repository_scan", Review.repository.in_(names), Review.user_id.in_(owner_ids)).order_by(Review.created_at.desc()).limit(1000)))
    result=_summary(rows); result.update({"team_id":team_id,"scope":"Scans for repositories shared with this team"})
    return result


@router.get("/remediations")
def list_remediations(user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    rows=list(db.scalars(select(Review).where(Review.user_id==user.id, Review.review_type=="repository_scan").order_by(Review.created_at.desc()).limit(200)))
    saved={(r.review_id,r.fingerprint):r for r in db.scalars(select(FindingRemediation).where(FindingRemediation.user_id==user.id))}
    output=[]
    for row in rows:
        for finding in _findings(row):
            fp=_fingerprint(finding); state=saved.get((row.review_id,fp))
            output.append({"review_id":row.review_id,"repository":row.repository,"created_at":row.created_at.isoformat() if row.created_at else None,
                           "fingerprint":fp,"finding":finding,"status":state.status if state else "open","note":state.note if state else ""})
    return output[:1000]


class RemediationUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_progress|resolved|accepted_risk|false_positive)$")
    note: str = Field(default="", max_length=2000)

@router.patch("/remediations/{review_id}/{fingerprint}")
def update_remediation(review_id:str, fingerprint:str, payload:RemediationUpdate, user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    row=db.scalar(select(Review).where(Review.review_id==review_id,Review.user_id==user.id,Review.review_type=="repository_scan"))
    if not row: raise HTTPException(404,"Repository scan not found.")
    finding=next((f for f in _findings(row) if _fingerprint(f)==fingerprint),None)
    if not finding: raise HTTPException(404,"Finding not found in this scan.")
    state=db.scalar(select(FindingRemediation).where(FindingRemediation.user_id==user.id,FindingRemediation.review_id==review_id,FindingRemediation.fingerprint==fingerprint))
    if not state:
        state=FindingRemediation(user_id=user.id,review_id=review_id,fingerprint=fingerprint); db.add(state)
    state.status=payload.status; state.note=payload.note.strip(); state.updated_at=datetime.now(timezone.utc)
    db.commit()
    record_audit(db,user.id,"security.remediation_updated","finding",fingerprint,{"review_id":review_id,"status":payload.status})
    return {"review_id":review_id,"fingerprint":fingerprint,"status":state.status,"note":state.note}


@router.get("/alerts")
def security_alerts(user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    rows=list(db.scalars(select(Review).where(Review.user_id==user.id,Review.review_type=="repository_scan").order_by(Review.created_at.desc()).limit(100)))
    states={(r.review_id,r.fingerprint):r.status for r in db.scalars(select(FindingRemediation).where(FindingRemediation.user_id==user.id))}
    alerts=[]
    for row in rows:
        for f in _findings(row):
            severity=str(f.get("severity","info")).lower()
            state=states.get((row.review_id,_fingerprint(f)),"open")
            if severity in {"critical","high"} and state not in {"resolved","accepted_risk","false_positive"}:
                alerts.append({"review_id":row.review_id,"repository":row.repository,"severity":severity,"title":f.get("title") or f.get("rule_id"),"file":f.get("file"),"status":state,"created_at":row.created_at.isoformat() if row.created_at else None})
    return {"count":len(alerts),"alerts":alerts[:100],"note":"Alerts are derived from saved scans; they are not push notifications."}


class ScheduleCreate(BaseModel):
    repository_id:int=Field(ge=1)
    cadence:str=Field(default="weekly",pattern="^(daily|weekly)$")

@router.get("/schedules")
def list_schedules(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(RepositorySchedule).where(RepositorySchedule.user_id==user.id).order_by(RepositorySchedule.created_at.desc()))
    return [{"id":r.id,"repository_id":r.repository_id,"cadence":r.cadence,"enabled":r.enabled,"created_at":r.created_at.isoformat(),"execution":"Requires an external scheduler/runner; CodeGuard does not retain GitHub credentials."} for r in rows]

@router.post("/schedules",status_code=201)
def create_schedule(payload:ScheduleCreate,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    repo=db.scalar(select(Repository).where(Repository.id==payload.repository_id,Repository.user_id==user.id))
    if not repo: raise HTTPException(404,"Registered repository not found.")
    existing=db.scalar(select(RepositorySchedule).where(RepositorySchedule.user_id==user.id,RepositorySchedule.repository_id==repo.id))
    if existing: existing.cadence=payload.cadence; existing.enabled=True; row=existing
    else: row=RepositorySchedule(user_id=user.id,repository_id=repo.id,cadence=payload.cadence); db.add(row)
    db.commit(); db.refresh(row)
    record_audit(db,user.id,"security.schedule_created","repository",str(repo.id),{"cadence":payload.cadence})
    return {"id":row.id,"repository_id":row.repository_id,"cadence":row.cadence,"enabled":row.enabled,"execution":"Configuration saved. Connect an external scheduler/runner to execute scans."}

@router.delete("/schedules/{schedule_id}",status_code=204)
def delete_schedule(schedule_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(RepositorySchedule).where(RepositorySchedule.id==schedule_id,RepositorySchedule.user_id==user.id))
    if not row: raise HTTPException(404,"Schedule not found.")
    db.delete(row); db.commit(); return Response(status_code=204)


def _report_rows(rows):
    out=[]
    for row in rows:
        for f in _findings(row):
            out.append({"repository":row.repository,"scan_id":row.review_id,"scanned_at":row.created_at.isoformat() if row.created_at else "",
                        "severity":f.get("severity","info"),"rule_id":f.get("rule_id",""),"title":f.get("title",""),"file":f.get("file",""),"line":f.get("line",""),"message":f.get("message","")})
    return out

@router.get("/reports/export")
def export_report(format:str="csv",user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=list(db.scalars(select(Review).where(Review.user_id==user.id,Review.review_type=="repository_scan").order_by(Review.created_at.desc()).limit(500)))
    data=_report_rows(rows); format=format.lower()
    if format=="csv":
        buffer=io.StringIO(); fields=["repository","scan_id","scanned_at","severity","rule_id","title","file","line","message"]
        writer=csv.DictWriter(buffer,fieldnames=fields); writer.writeheader(); writer.writerows(data)
        return Response(buffer.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=codeguard-security-report.csv"})
    if format=="xlsx":
        from openpyxl import Workbook
        wb=Workbook(); ws=wb.active; ws.title="Security Findings"
        fields=list(data[0].keys()) if data else ["repository","scan_id","scanned_at","severity","rule_id","title","file","line","message"]
        ws.append(fields)
        for item in data: ws.append([item.get(k,"") for k in fields])
        ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
        stream=io.BytesIO(); wb.save(stream)
        return Response(stream.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=codeguard-security-report.xlsx"})
    if format=="pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        stream=io.BytesIO(); doc=SimpleDocTemplate(stream,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24)
        styles=getSampleStyleSheet(); story=[Paragraph("CodeGuard AI – Security Findings Report",styles["Title"]),Paragraph(f"Generated {datetime.now(timezone.utc).isoformat()} · {len(data)} findings",styles["Normal"]),Spacer(1,12)]
        table_data=[["Repository","Severity","Rule","Finding","File","Line"]]
        table_data += [[str(x.get("repository",""))[:35],str(x.get("severity","")),str(x.get("rule_id",""))[:20],str(x.get("title",""))[:55],str(x.get("file",""))[:45],str(x.get("line",""))] for x in data[:1000]]
        table=Table(table_data,repeatRows=1,colWidths=[105,55,75,180,130,35]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#203047")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f2f5f8")])]))
        story.append(table); doc.build(story)
        return Response(stream.getvalue(),media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=codeguard-security-report.pdf"})
    raise HTTPException(400,"Supported formats: csv, xlsx, pdf.")
