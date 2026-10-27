"""create recommendations

Revision ID: c4f1a9e2b6d3
Revises: 9fac4355b65e
Create Date: 2026-10-02 00:00:00.000000

Brick 12 — Recommendation Engine (candidate generation only). Creates
the recommendations table plus three native Postgres enum types
(recommendation_category, recommendation_risk_level,
recommendation_state). Enum values are the Python enum MEMBER NAMES
(uppercase), matching the confirmed behavior of every prior
Enum(PythonEnumClass) column in this project (transaction_type,
metric_status, etc.) — not `.value` (lowercase).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c4f1a9e2b6d3'
down_revision: Union[str, None] = '9fac4355b65e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATEGORY_VALUES = ['EMERGENCY_FUND', 'SAVINGS', 'DEBT', 'BUDGETING']
_RISK_LEVEL_VALUES = ['LOW', 'MEDIUM', 'HIGH']
_STATE_VALUES = [
    'CANDIDATE', 'VALIDATED', 'APPROVED', 'MODIFIED', 'BLOCKED',
    'CLARIFY', 'ESCALATE', 'PRESENTED', 'ACCEPTED', 'REJECTED',
    'IGNORED', 'EVALUATED',
]


def upgrade() -> None:
    # Deliberately NOT pre-created with an explicit .create() call here —
    # unlike the alter_column case in migration 9fac4355b65e,
    # op.create_table() auto-creates ENUM type columns itself. Pre-creating
    # them first (as an earlier version of this migration did) causes a
    # DuplicateObject error when create_table then tries to create the
    # same type again — caught by running this migration for real.
    # create_type=False tells SQLAlchemy not to attempt to create/drop
    # the type as part of this column's own DDL events, since
    # create_table's table-level DDL already handles creation once per
    # type (matching migration 8cbc766bb7dd's plain-Enum-in-create_table
    # pattern, extended here to three enum types instead of one).
    category_enum = postgresql.ENUM(*_CATEGORY_VALUES, name='recommendation_category')
    risk_level_enum = postgresql.ENUM(*_RISK_LEVEL_VALUES, name='recommendation_risk_level')
    state_enum = postgresql.ENUM(*_STATE_VALUES, name='recommendation_state')

    op.create_table(
        'recommendations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('category', category_enum, nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column('risk_level', risk_level_enum, nullable=False),
        sa.Column('state', state_enum, nullable=False),
        sa.Column('suitability_status', sa.String(length=50), nullable=True),
        sa.Column('source_references', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('based_on', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('rule_id', sa.String(length=100), nullable=False),
        sa.Column('policy_version', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recommendations_user_id'), 'recommendations', ['user_id'], unique=False)
    op.create_index(op.f('ix_recommendations_category'), 'recommendations', ['category'], unique=False)
    op.create_index(op.f('ix_recommendations_state'), 'recommendations', ['state'], unique=False)
    op.create_index(op.f('ix_recommendations_rule_id'), 'recommendations', ['rule_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recommendations_rule_id'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_state'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_category'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_user_id'), table_name='recommendations')
    op.drop_table('recommendations')
    sa.Enum(name='recommendation_state').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='recommendation_risk_level').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='recommendation_category').drop(op.get_bind(), checkfirst=True)
