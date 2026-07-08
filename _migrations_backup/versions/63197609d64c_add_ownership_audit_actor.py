"""
add ownership audit actor

Revision ID: 63197609d64c
Revises: 1134aaba51d3
Create Date: 2026-07-02 14:14:53.291289

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "63197609d64c"
down_revision: Union[str, Sequence[str], None] = "1134aaba51d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "fhir_servers", sa.Column("owner_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_fhir_servers_owner_id", "fhir_servers", ["owner_id"])
    op.create_foreign_key(
        "fk_fhir_servers_owner_id_users",
        "fhir_servers",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "audit_logs", sa.Column("actor_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_foreign_key(
        "fk_audit_logs_actor_id_users",
        "audit_logs",
        "users",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("audit_logs", "executed_by")


def downgrade():
    op.add_column("audit_logs", sa.Column("executed_by", sa.String(), nullable=True))
    op.drop_constraint("fk_audit_logs_actor_id_users", "audit_logs", type_="foreignkey")
    op.drop_index("ix_audit_logs_actor_id", "audit_logs")
    op.drop_column("audit_logs", "actor_id")
    op.drop_constraint(
        "fk_fhir_servers_owner_id_users", "fhir_servers", type_="foreignkey"
    )
    op.drop_index("ix_fhir_servers_owner_id", "fhir_servers")
    op.drop_column("fhir_servers", "owner_id")
