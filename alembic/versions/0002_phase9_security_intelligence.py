"""Add remediation tracking and repository scan schedules."""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0002_phase9_security_intelligence"
down_revision = "0001_phase6_security"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "finding_remediations" not in tables:
        op.create_table(
            "finding_remediations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("review_id", sa.String(64), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="open"),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "user_id", "review_id", "fingerprint", name="uq_finding_remediation"
            ),
        )
        op.create_index("ix_finding_remediations_user_id", "finding_remediations", ["user_id"])
        op.create_index("ix_finding_remediations_review_id", "finding_remediations", ["review_id"])
    if "repository_schedules" not in tables:
        op.create_table(
            "repository_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "repository_id",
                sa.Integer(),
                sa.ForeignKey("repositories.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("cadence", sa.String(16), nullable=False, server_default="weekly"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_repository_schedules_user_id", "repository_schedules", ["user_id"])
        op.create_index(
            "ix_repository_schedules_repository_id", "repository_schedules", ["repository_id"]
        )


def downgrade():
    op.drop_table("repository_schedules")
    op.drop_table("finding_remediations")
