"""Create BSIE investigation persistence foundation."""

from __future__ import annotations

from alembic import op
from sqlmodel import SQLModel

from persistence import legacy_models, models  # noqa: F401
from persistence.base import Base


revision = "20260330_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    SQLModel.metadata.drop_all(bind=bind)
