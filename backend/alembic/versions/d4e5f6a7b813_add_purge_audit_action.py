"""add purge audit action

Revision ID: d4e5f6a7b813
Revises: c3d2e5f6a712
Create Date: 2026-08-13 00:10:00.000000

Adds PURGE to the auditaction enum: the admin-only "delete invalid_resources
rows from Verity's own database, without touching the source FHIR server"
action gets its own audit entries alongside DELETE/PATCH.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b813"
down_revision: Union[str, Sequence[str], None] = "c3d2e5f6a712"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'PURGE'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; removing PURGE would require
    # rebuilding the type. Left as a no-op — harmless to leave the value
    # defined even after downgrading the code that uses it.
    pass
