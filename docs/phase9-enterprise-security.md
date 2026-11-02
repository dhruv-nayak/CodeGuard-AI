# Phase 9 — Enterprise Security & Intelligence

## Scope

Phase 9 adds a first pass at security operations around the repository scans introduced in Phase 8: risk summaries, trends, team aggregation, remediation state, high-severity alert views, exportable reports and schedule configuration.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/security/dashboard` | Per-user scan summary, severity distribution, daily trend and remediation-state counts |
| `GET /api/v1/security/teams/{team_id}/dashboard` | Aggregate scan summary for repositories shared with a team; requires membership or admin |
| `GET /api/v1/security/remediations` | Findings from the authenticated user's saved repository scans and their current state |
| `PATCH /api/v1/security/remediations/{review_id}/{fingerprint}` | Update finding state and note |
| `GET /api/v1/security/alerts` | Unresolved critical/high signals from saved scans |
| `GET /api/v1/security/reports/export?format=csv` | CSV export |
| `GET /api/v1/security/reports/export?format=xlsx` | Excel export |
| `GET /api/v1/security/reports/export?format=pdf` | PDF export |
| `GET /api/v1/security/schedules` | List schedule configuration |
| `POST /api/v1/security/schedules` | Create/update a daily or weekly schedule configuration |
| `DELETE /api/v1/security/schedules/{schedule_id}` | Delete an owned schedule |

### Remediation request

```json
{
  "status": "in_progress",
  "note": "Fix is being prepared for the next release."
}
```

Supported statuses: `open`, `in_progress`, `resolved`, `accepted_risk`, `false_positive`.

## Risk scoring and trend semantics

The risk score starts at 100 and subtracts 15 per critical, 8 per high, 4 per medium and 1 per low finding, clamped to 0–100. This simple heuristic is intentionally explainable; it is not CVSS, exploitability analysis, or a compliance score. Daily trends use scan timestamps and count findings from each saved snapshot. Repeated findings across snapshots may be counted more than once.

Remediation records are scoped to the user, scan ID and stable finding fingerprint. A finding in a later scan can have a different scan ID and therefore needs a new status decision. Resolved, accepted-risk and false-positive items are omitted from the high-priority alert list for that scan.

## Team data boundary

A team dashboard is accessible only to a team member or administrator. It aggregates saved repository scans associated with repositories registered and shared through that team. It does not grant GitHub access and does not bypass GitHub permissions.

## Scheduled rescans and notifications — explicit limitation

The schedule API stores daily/weekly preferences against a repository registered by the requesting user. This release does **not** include an in-process scheduler, worker queue, token vault, or credential persistence. A separately operated scheduler/runner must read the configuration, acquire an authorized GitHub credential at run time, and call the existing repository scan API. The dashboard alert endpoint is a pull-based view of saved scan findings; it does not send email, Slack, webhook or push notifications.

This boundary avoids storing long-lived GitHub tokens merely to enable unattended scans. Do not treat a saved schedule as proof that a scan has run.

## Reports

CSV, XLSX and PDF exports contain saved repository finding rows: repository, scan ID/time, severity, rule ID, title, file, line and message. Exports are user-scoped and should be stored and shared as sensitive security data. They do not include source code or credentials.

## Database migration

Alembic revision `0002_phase9_security_intelligence` creates `finding_remediations` and `repository_schedules`. Startup upgrades to the latest migration. Back up the database and test upgrades against a restored copy before deployment.

## Validation and known limitations

- Automated tests cover authenticated dashboard access, scan-derived findings, remediation updates, alert filtering, schedule ownership, team access denial and CSV/XLSX/PDF generation.
- Migration was tested on a fresh SQLite database; the normal test run also exercised the existing local project database.
- Live GitHub, OSV, email/webhook and external scheduler integrations were not exercised by these tests.
- Risk scoring and static findings are heuristic. Security review and operational controls remain necessary before production use.
