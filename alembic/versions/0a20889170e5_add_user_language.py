"""add user language

Revision ID: 0a20889170e5
Revises: 5cb45ef2382c
Create Date: 2026-09-15 01:40:15.524892

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a20889170e5"
down_revision: str | Sequence[str] | None = "5cb45ef2382c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(8)))


def downgrade() -> None:
    op.drop_column("users", "language")
