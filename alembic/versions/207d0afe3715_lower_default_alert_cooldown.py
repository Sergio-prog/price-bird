"""lower default alert cooldown

Revision ID: 207d0afe3715
Revises: 2b9f275a34e2
Create Date: 2026-09-24 21:53:57.410095

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "207d0afe3715"
down_revision: str | Sequence[str] | None = "2b9f275a34e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("alerts", "cooldown_seconds", server_default="10")
    op.execute("UPDATE alerts SET cooldown_seconds = 10 WHERE cooldown_seconds = 900 AND status IN ('active', 'paused')")


def downgrade() -> None:
    op.alter_column("alerts", "cooldown_seconds", server_default="900")
