"""server delete audit, drop purge entries and verification_result

Revision ID: f6a7b8c9da15
Revises: e5f6a7b8c914
Create Date: 2026-10-21 00:00:00.000000

- audit_logs.server_id becomes nullable with ON DELETE SET NULL, so the audit
  history of a deleted server is kept. New action SERVER_DELETE.
- Audit rows with action PURGE are removed; the DB purge endpoint is gone.
  The enum value itself stays (Postgres has no DROP VALUE).
- validation_runs.verification_result is dropped; runs are summarised in
  test_report and on the FHIR server as a List.
- Corrected descriptions of photo_forbidden and the period rules in stored
  configs, as long as they still carry the old default text.
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9da15"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "audit_logs_server_id_fkey"

DESCRIPTION_FIXES = {
    "photo_forbidden": (
        "Checks whether the field 'name' is present",
        "Checks whether the field 'photo' is present.",
    ),
    "period_end_after_start": (
        "If period.end is present, it must be after period.start. ",
        "If period.end is present, it must not be before period.start "
        "(FHIR invariant per-1). Values are compared at the precision of the "
        "less precise one.",
    ),
    "effective_period_end_after_start": (
        "If effectivePeriod is used, end must be after start. ",
        "If effectivePeriod is used, end must not be before start "
        "(FHIR invariant per-1).",
    ),
}


def _fix_descriptions(direction: int) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, rules FROM validation_configs")).fetchall()
    for row_id, rules in rows:
        if isinstance(rules, str):
            rules = json.loads(rules)
        changed = False
        for key, texts in DESCRIPTION_FIXES.items():
            old, new = texts if direction > 0 else texts[::-1]
            rule = rules.get(key)
            if isinstance(rule, dict) and rule.get("description") == old:
                rule["description"] = new
                changed = True
        if changed:
            conn.execute(
                sa.text("UPDATE validation_configs SET rules = :rules WHERE id = :id"),
                {"rules": json.dumps(rules), "id": row_id},
            )


def upgrade() -> None:
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'SERVER_DELETE'")

    op.drop_constraint(FK_NAME, "audit_logs", type_="foreignkey")
    op.alter_column("audit_logs", "server_id", nullable=True)
    op.create_foreign_key(
        FK_NAME,
        "audit_logs",
        "fhir_servers",
        ["server_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("DELETE FROM audit_logs WHERE action = 'PURGE'")

    op.drop_column("validation_runs", "verification_result")

    _fix_descriptions(+1)


def downgrade() -> None:
    _fix_descriptions(-1)

    op.add_column(
        "validation_runs",
        sa.Column("verification_result", sa.JSON(), nullable=True),
    )

    # Entries of deleted servers cannot point to a server any more.
    op.execute("DELETE FROM audit_logs WHERE server_id IS NULL")
    op.drop_constraint(FK_NAME, "audit_logs", type_="foreignkey")
    op.alter_column("audit_logs", "server_id", nullable=False)
    op.create_foreign_key(
        FK_NAME,
        "audit_logs",
        "fhir_servers",
        ["server_id"],
        ["id"],
        ondelete="CASCADE",
    )
