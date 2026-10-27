"""add controlled category taxonomy to transactions

Revision ID: 9fac4355b65e
Revises: 3a0705da8fb4
Create Date: 2026-09-22 06:30:00.000000

Hand-written (no live DB/network access in this session — see the
README's verification note for this brick). Converts
transactions.category from a free-text String(100) to the controlled
TransactionCategory enum (app/models/transaction.py) and makes it
NOT NULL — the table has no CRUD API before this brick, so it should
be empty in every environment this migration will run against.

Enum values are the Python enum MEMBER NAMES (uppercase), not `.value`
(lowercase) — matching how SQLAlchemy's Enum(PythonEnumClass) actually
serializes str-subclassed enums, confirmed against the already-verified
transaction_type enum in migration 8cbc766bb7dd, which stores 'INCOME'/
'EXPENSE', not 'income'/'expense'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9fac4355b65e'
down_revision: Union[str, None] = '3a0705da8fb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATEGORY_VALUES = [
    'SALARY', 'BUSINESS_INCOME', 'INVESTMENT_INCOME', 'RENTAL_INCOME',
    'GIFT_RECEIVED', 'REFUND', 'OTHER_INCOME',
    'HOUSING', 'UTILITIES', 'GROCERIES', 'TRANSPORTATION', 'HEALTHCARE',
    'INSURANCE', 'DEBT_PAYMENT', 'DINING_OUT', 'ENTERTAINMENT', 'SHOPPING',
    'EDUCATION', 'PERSONAL_CARE', 'SUBSCRIPTIONS', 'TRAVEL', 'OTHER_EXPENSE',
    'UNCATEGORIZED',
]


def upgrade() -> None:
    category_enum = postgresql.ENUM(*_CATEGORY_VALUES, name='transaction_category')
    # alter_column does not auto-create the enum type the way create_table
    # does (same gotcha as migration 55960cb776ac) — create it explicitly.
    category_enum.create(op.get_bind(), checkfirst=True)

    op.alter_column(
        'transactions',
        'category',
        existing_type=sa.String(length=100),
        type_=category_enum,
        postgresql_using='category::transaction_category',
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'transactions',
        'category',
        existing_type=postgresql.ENUM(*_CATEGORY_VALUES, name='transaction_category'),
        type_=sa.String(length=100),
        postgresql_using='category::text',
        nullable=True,
    )
    sa.Enum(name='transaction_category').drop(op.get_bind(), checkfirst=True)
