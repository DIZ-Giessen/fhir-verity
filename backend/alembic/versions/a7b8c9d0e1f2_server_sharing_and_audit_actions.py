"""server sharing, audit for settings changes, drop unused columns

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9da15
Create Date: 2026-10-22 00:00:00.000000

- server_members: servers can be shared with users besides the owner.
- New audit actions SERVER_AUTH_CHANGE, SERVER_SHARE, SERVER_UNSHARE and
  USER_ROLE_CHANGE; audit_logs.server_base_url becomes nullable because a
  role change concerns no server.
- invalid_resources: drop raw_resource, anomaly_score, risk_score and
  llm_suggestions, which were never written.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9da15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_ACTIONS = (
    "SERVER_AUTH_CHANGE",
    "SERVER_SHARE",
    "SERVER_UNSHARE",
    "USER_ROLE_CHANGE",
)


def upgrade() -> None:
    op.create_table(
        "server_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("added_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["fhir_servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_id", "user_id", name="uq_server_members_server_user"),
    )
    op.create_index("ix_server_members_server_id", "server_members", ["server_id"])
    op.create_index("ix_server_members_user_id", "server_members", ["user_id"])

    for action in NEW_ACTIONS:
        op.execute(f"ALTER TYPE auditaction ADD VALUE IF NOT EXISTS '{action}'")
    op.alter_column("audit_logs", "server_base_url", nullable=True)

    op.drop_column("invalid_resources", "raw_resource")
    op.drop_column("invalid_resources", "anomaly_score")
    op.drop_column("invalid_resources", "risk_score")
    op.drop_column("invalid_resources", "llm_suggestions")


def downgrade() -> None:
    op.add_column("invalid_resources", sa.Column("llm_suggestions", sa.JSON(), nullable=True))
    op.add_column("invalid_resources", sa.Column("risk_score", sa.Float(), nullable=True))
    op.add_column("invalid_resources", sa.Column("anomaly_score", sa.Float(), nullable=True))
    op.add_column("invalid_resources", sa.Column("raw_resource", sa.JSON(), nullable=True))

    # Enum values stay (Postgres has no DROP VALUE), their rows must go.
    op.execute(
        "DELETE FROM audit_logs WHERE action IN ("
        + ", ".join(f"'{a}'" for a in NEW_ACTIONS)
        + ")"
    )
    op.alter_column("audit_logs", "server_base_url", nullable=False)

    op.drop_index("ix_server_members_user_id", table_name="server_members")
    op.drop_index("ix_server_members_server_id", table_name="server_members")
    op.drop_table("server_members")
