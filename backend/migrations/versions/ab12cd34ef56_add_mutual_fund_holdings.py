"""Add persistent user-entered mutual-fund holdings."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "ab12cd34ef56"
down_revision: Union[str, None] = "f20a1b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mutual_fund_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheme_code", sa.Integer(), nullable=False),
        sa.Column("scheme_name", sa.String(300), nullable=False),
        sa.Column("units", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount_invested", sa.Numeric(14, 2)),
        sa.Column("monthly_sip", sa.Numeric(14, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.CheckConstraint("units > 0", name="ck_mf_holding_units_positive"),
        sa.CheckConstraint("amount_invested IS NULL OR amount_invested >= 0", name="ck_mf_holding_invested_nonnegative"),
        sa.CheckConstraint("monthly_sip IS NULL OR monthly_sip >= 0", name="ck_mf_holding_sip_nonnegative"),
    )
    op.create_index("ix_mutual_fund_holdings_user_id", "mutual_fund_holdings", ["user_id"])
    op.create_index("ix_mutual_fund_holdings_scheme_code", "mutual_fund_holdings", ["scheme_code"])


def downgrade() -> None:
    op.drop_index("ix_mutual_fund_holdings_scheme_code", table_name="mutual_fund_holdings")
    op.drop_index("ix_mutual_fund_holdings_user_id", table_name="mutual_fund_holdings")
    op.drop_table("mutual_fund_holdings")
