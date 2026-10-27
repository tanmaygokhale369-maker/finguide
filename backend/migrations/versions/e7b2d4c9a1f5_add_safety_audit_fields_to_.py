"""add safety audit fields to recommendations

Revision ID: e7b2d4c9a1f5
Revises: c4f1a9e2b6d3
Create Date: 2026-10-02 00:00:00.000000

Brick 13 — Safety & Suitability Layer. Adds two columns the gate needs
for its audit trail (Pack 02's "Audit Fields": safety_status + an
explanation). safety_status itself is NOT a new column — Brick 13
writes it into the existing `suitability_status` column from Brick 12
(see app/services/safety_suitability_service.py's module docstring for
why). Both new columns are nullable/defaulted, so this is purely
additive — no existing row's meaning changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7b2d4c9a1f5'
down_revision: Union[str, None] = 'c4f1a9e2b6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recommendations', sa.Column('safety_explanation', sa.Text(), nullable=True))
    op.add_column(
        'recommendations',
        sa.Column(
            'safety_checks',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='[]',
        ),
    )


def downgrade() -> None:
    op.drop_column('recommendations', 'safety_checks')
    op.drop_column('recommendations', 'safety_explanation')
