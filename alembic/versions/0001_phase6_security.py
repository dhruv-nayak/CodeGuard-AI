"""Create the Phase 5 schema when absent and add session revocation version.

Revision ID: 0001_phase6_security
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_phase6_security"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(320), nullable=False, unique=True),
            sa.Column("full_name", sa.String(120), nullable=False),
            sa.Column("password_hash", sa.String(512), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        tables.add("users")
    elif "token_version" not in {column["name"] for column in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(
                sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
            )

    if "reviews" not in tables:
        op.create_table(
            "reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("review_id", sa.String(64), nullable=False, unique=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("review_type", sa.String(30), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("repository", sa.String(255), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
        op.create_index("ix_reviews_created_at", "reviews", ["created_at"])

    if "repositories" not in tables:
        op.create_table(
            "repositories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("owner", sa.String(100), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("default_branch", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "owner", "name", name="uq_user_repository"),
        )
        op.create_index("ix_repositories_user_id", "repositories", ["user_id"])

    if "teams" not in tables:
        op.create_table(
            "teams",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False, unique=True),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "team_members" not in tables:
        op.create_table(
            "team_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("member_role", sa.String(30), nullable=False),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("team_id", "user_id", name="uq_team_member"),
        )
        op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
        op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    if "team_repositories" not in tables:
        op.create_table(
            "team_repositories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "repository_id", sa.Integer(),
                sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("team_id", "repository_id", name="uq_team_repository"),
        )
        op.create_index("ix_team_repositories_team_id", "team_repositories", ["team_id"])
        op.create_index(
            "ix_team_repositories_repository_id", "team_repositories", ["repository_id"]
        )

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("resource_type", sa.String(60), nullable=False),
            sa.Column("resource_id", sa.String(120), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade():
    # Deliberately retain application tables and user data; only remove the Phase 6 column.
    bind = op.get_bind()
    if inspect(bind).has_table("users"):
        columns = {column["name"] for column in inspect(bind).get_columns("users")}
        if "token_version" in columns:
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("token_version")
