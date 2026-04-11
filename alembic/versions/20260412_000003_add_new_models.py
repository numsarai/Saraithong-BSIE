"""Add User, Alert, GraphAnnotation models and Transaction.analyst_note

Revision ID: 20260412_000003
Revises: 20260411_000002
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = "20260412_000003"
down_revision = "20260411_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("role", sa.String(32), nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("oauth_provider", sa.String(64)),
        sa.Column("oauth_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # Alerts table
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id")),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id")),
        sa.Column("parser_run_id", sa.String(36), sa.ForeignKey("parser_runs.id")),
        sa.Column("rule_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("finding_id", sa.String(128)),
        sa.Column("summary", sa.Text),
        sa.Column("evidence_json", sa.JSON),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_rule_type", "alerts", ["rule_type"])
    op.create_index("ix_alerts_account_id", "alerts", ["account_id"])

    # Graph annotations table
    op.create_table(
        "graph_annotations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("annotation_type", sa.String(32), nullable=False, server_default="note"),
        sa.Column("content", sa.Text),
        sa.Column("tag", sa.String(64)),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="analyst"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_graph_annotations_node_id", "graph_annotations", ["node_id"])

    # Add analyst_note to transactions (if not already added)
    try:
        op.add_column("transactions", sa.Column("analyst_note", sa.Text))
    except Exception:
        pass  # Column may already exist from manual ALTER TABLE


def downgrade() -> None:
    op.drop_table("graph_annotations")
    op.drop_table("alerts")
    op.drop_table("users")
    try:
        op.drop_column("transactions", "analyst_note")
    except Exception:
        pass
