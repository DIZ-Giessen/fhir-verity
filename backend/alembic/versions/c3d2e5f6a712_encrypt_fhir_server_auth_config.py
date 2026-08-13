"""encrypt fhir_server auth_config at rest

Revision ID: c3d2e5f6a712
Revises: b2c1d4e5f601
Create Date: 2026-08-13 00:05:00.000000

Data-only migration: fhir_servers.auth_config kept storing Basic-Auth
passwords and OAuth2 client secrets as plaintext JSON. The column stays
`json` (see app.core.crypto.EncryptedJSON) - what changes is the value
stored in it, from a plain JSON object to a single JSON string holding
the Fernet ciphertext. Requires FIELD_ENCRYPTION_KEY to be set.
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.crypto import encrypt_json, decrypt_json


# revision identifiers, used by Alembic.
revision: str = "c3d2e5f6a712"
down_revision: Union[str, Sequence[str], None] = "b2c1d4e5f601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, auth_config::text AS auth_config FROM fhir_servers "
            "WHERE auth_config IS NOT NULL"
        )
    ).fetchall()
    for row in rows:
        parsed = json.loads(row.auth_config)
        if not isinstance(parsed, dict):
            # Already a JSON string -> already encrypted (safe to re-run).
            continue
        encrypted = encrypt_json(parsed)
        conn.execute(
            sa.text("UPDATE fhir_servers SET auth_config = CAST(:val AS json) WHERE id = :id"),
            {"val": json.dumps(encrypted), "id": row.id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, auth_config::text AS auth_config FROM fhir_servers "
            "WHERE auth_config IS NOT NULL"
        )
    ).fetchall()
    for row in rows:
        parsed = json.loads(row.auth_config)
        if not isinstance(parsed, str):
            # Already a plain object -> nothing to decrypt.
            continue
        plain = decrypt_json(parsed)
        conn.execute(
            sa.text("UPDATE fhir_servers SET auth_config = CAST(:val AS json) WHERE id = :id"),
            {"val": json.dumps(plain), "id": row.id},
        )
