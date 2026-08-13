"""one running validation run per server

Revision ID: b2c1d4e5f601
Revises: ff80abafee59
Create Date: 2026-08-13 00:00:00.000000

Partial unique index so at most one RUNNING validation run can exist per
server_id at a time. Backs up the application-level check in
validation.py (_assert_no_running_run) against a true concurrent
double-start, which a plain SELECT-then-INSERT can't rule out on its own.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c1d4e5f601"
down_revision: Union[str, Sequence[str], None] = "ff80abafee59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_validation_runs_one_running_per_server",
        "validation_runs",
        ["server_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validation_runs_one_running_per_server",
        table_name="validation_runs",
    )
