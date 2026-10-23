"""rule defaults come from the rule registry

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-23 00:00:00.000000

The defaults of every rule are now defined in code (app/services/rules) and
no longer copied into validation_configs rows with server_id NULL. Those rows
could not be edited in the UI and were never updated for new rules, so they
are removed. Server overrides are kept.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM validation_configs WHERE server_id IS NULL")


def downgrade() -> None:
    # The previous version recreates the global rows on startup.
    pass
