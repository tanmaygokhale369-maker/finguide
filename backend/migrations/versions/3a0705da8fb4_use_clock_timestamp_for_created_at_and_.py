"""use clock_timestamp for created_at and updated_at defaults

Revision ID: 3a0705da8fb4
Revises: 1d87df5a0882
Create Date: 2026-09-17 06:07:04.536944

Alembic's autogenerate does not detect server_default changes unless
`compare_server_default=True` is set in env.py (it isn't here), so this
migration is written by hand rather than generated.

Postgres's now() returns the *transaction's* start time, identical for
every row inserted within one transaction. clock_timestamp() returns the
true wall-clock time at each statement — required for any code that
orders rows by created_at to determine actual sequence (e.g. metrics
history, "most recent value" reasoning in Brick 08's validation).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a0705da8fb4'
down_revision: Union[str, None] = '1d87df5a0882'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table using TimestampMixin as of this migration.
_TABLES = [
    "users",
    "financial_profiles",
    "transactions",
    "conversations",
    "messages",
    "extracted_fields",
    "derived_metrics",
]


def upgrade() -> None:
    for table in _TABLES:
        op.alter_column(table, "created_at", server_default=sa.text("clock_timestamp()"))
        op.alter_column(table, "updated_at", server_default=sa.text("clock_timestamp()"))


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(table, "created_at", server_default=sa.text("now()"))
        op.alter_column(table, "updated_at", server_default=sa.text("now()"))
