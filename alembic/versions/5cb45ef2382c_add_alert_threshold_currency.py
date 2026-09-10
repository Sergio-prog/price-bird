"""add alert threshold currency

Revision ID: 5cb45ef2382c
Revises: f23d5634ec96
Create Date: 2026-09-10 20:39:40.036808

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5cb45ef2382c"
down_revision: str | Sequence[str] | None = "f23d5634ec96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("threshold_currency", sa.String(16), nullable=False, server_default="USD"),
    )


def downgrade() -> None:
    op.drop_column("alerts", "threshold_currency")
