"""Add posted_date index, unique constraint on account_entity_links, cleanup low-confidence matches.

Revision ID: 20260411_000002
Revises: 20260330_000001
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = "20260411_000002"
down_revision = "20260330_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add index on transactions.posted_date for date-range queries
    op.create_index(
        "ix_transactions_posted_date",
        "transactions",
        ["posted_date"],
        if_not_exists=True,
    )

    # 2. Clean duplicate account_entity_links before adding unique constraint
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM account_entity_links
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM account_entity_links
            GROUP BY account_id, entity_id, link_type
        )
    """))

    # 3. Add unique constraint on account_entity_links
    op.create_unique_constraint(
        "uq_account_entity_link",
        "account_entity_links",
        ["account_id", "entity_id", "link_type"],
    )

    # 4. Cleanup low-confidence suggested matches
    result = conn.execute(sa.text("""
        DELETE FROM transaction_matches
        WHERE status = 'suggested'
          AND confidence_score < 0.3
    """))
    print(f"  Cleaned {result.rowcount} low-confidence matches")


def downgrade() -> None:
    op.drop_constraint("uq_account_entity_link", "account_entity_links", type_="unique")
    op.drop_index("ix_transactions_posted_date", "transactions")
