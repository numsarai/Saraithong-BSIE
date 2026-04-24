"""Add bank template variants

Revision ID: 20260424_000004
Revises: 20260412_000003
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = "20260424_000004"
down_revision = "20260412_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_template_variants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bank_key", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="excel"),
        sa.Column("sheet_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("header_row", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ordered_signature", sa.String(64), nullable=False),
        sa.Column("set_signature", sa.String(64), nullable=False),
        sa.Column("layout_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("column_order_json", sa.JSON, nullable=False),
        sa.Column("confirmed_mapping_json", sa.JSON, nullable=False),
        sa.Column("trust_state", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confirmation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("correction_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confirmed_by_json", sa.JSON, nullable=False),
        sa.Column("dry_run_summary_json", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_by", sa.String(255)),
        sa.Column("notes", sa.Text),
        sa.UniqueConstraint(
            "bank_key",
            "source_type",
            "ordered_signature",
            "sheet_name",
            "header_row",
            name="uq_bank_template_variant_signature",
        ),
    )
    op.create_index(
        "ix_bank_template_variants_bank_trust",
        "bank_template_variants",
        ["bank_key", "trust_state"],
    )
    op.create_index(
        "ix_bank_template_variants_set_signature",
        "bank_template_variants",
        ["set_signature"],
    )
    op.create_index(
        "ix_bank_template_variants_trust_state",
        "bank_template_variants",
        ["trust_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_template_variants_trust_state", table_name="bank_template_variants")
    op.drop_index("ix_bank_template_variants_set_signature", table_name="bank_template_variants")
    op.drop_index("ix_bank_template_variants_bank_trust", table_name="bank_template_variants")
    op.drop_table("bank_template_variants")
