"""Add dated manual activity ledger for mutual-fund holdings."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "bc23de45fa67"
down_revision: Union[str, None] = "ab12cd34ef56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("mutual_fund_holdings", sa.Column("redemption_proceeds", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.create_table(
        "holding_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("holding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mutual_fund_holdings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("units_delta", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.CheckConstraint("activity_type IN ('opening_balance','purchase','redemption','adjustment')", name="ck_holding_activity_type"),
        sa.CheckConstraint("units_delta <> 0", name="ck_holding_activity_units_nonzero"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_holding_activity_amount_nonnegative"),
        sa.CheckConstraint("(activity_type = 'redemption' AND units_delta < 0) OR (activity_type <> 'redemption' AND units_delta > 0) OR activity_type = 'adjustment'", name="ck_holding_activity_sign"),
    )
    op.create_index("ix_holding_activities_user_id", "holding_activities", ["user_id"])
    op.create_index("ix_holding_activities_holding_id", "holding_activities", ["holding_id"])
    op.create_index("ix_holding_activities_activity_date", "holding_activities", ["activity_date"])
    op.execute("""
        INSERT INTO holding_activities
            (id, user_id, holding_id, activity_type, units_delta, amount, activity_date, note, created_at, updated_at)
        SELECT gen_random_uuid(), user_id, id, 'opening_balance', units, amount_invested,
               created_at::date, 'Opening balance migrated from saved holding; exact purchase date was not recorded.',
               created_at, updated_at
        FROM mutual_fund_holdings
    """)


def downgrade() -> None:
    op.drop_index("ix_holding_activities_activity_date", table_name="holding_activities")
    op.drop_index("ix_holding_activities_holding_id", table_name="holding_activities")
    op.drop_index("ix_holding_activities_user_id", table_name="holding_activities")
    op.drop_table("holding_activities")
    op.drop_column("mutual_fund_holdings", "redemption_proceeds")
