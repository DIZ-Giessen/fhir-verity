"""server delete cascade, report toggle and bulk audit actions

Revision ID: e5f6a7b8c914
Revises: d4e5f6a7b813
Create Date: 2026-09-24 00:00:00.000000

- validation_runs.server_id now cascades on delete like every other table
  referencing fhir_servers. Without it, deleting a server that already had
  runs failed with a foreign-key violation.
- fhir_servers.write_fhir_reports: per-server switch for posting
  TestScript/TestReport/VerificationResult back to the FHIR server.
- BULK_DELETE / BULK_PATCH audit actions: bulk operations write one summary
  row instead of one row per resource.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c914"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b813"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "validation_runs_server_id_fkey"


def upgrade() -> None:
    op.drop_constraint(FK_NAME, "validation_runs", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "validation_runs",
        "fhir_servers",
        ["server_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column(
        "fhir_servers",
        sa.Column(
            "write_fhir_reports",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'BULK_DELETE'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'BULK_PATCH'")


def downgrade() -> None:
    # Enum values stay (Postgres has no DROP VALUE), see d4e5f6a7b813.
    op.drop_column("fhir_servers", "write_fhir_reports")

    op.drop_constraint(FK_NAME, "validation_runs", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        "validation_runs",
        "fhir_servers",
        ["server_id"],
        ["id"],
    )
