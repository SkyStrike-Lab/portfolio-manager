"""Add option_deliveries table

Revision ID: 016
Revises: 015
Create Date: 2026-10-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'option_deliveries',
        sa.Column('delivery_id', sa.Text(), primary_key=True, nullable=False),
        sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id', ondelete='SET NULL')),
        sa.Column('symbol', sa.Text(), nullable=False),
        sa.Column('delivery_type', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('shares', sa.Integer(), nullable=False),
        sa.Column('strike_price', sa.Float(), nullable=False),
        sa.Column('effective_basis', sa.Float(), nullable=False),
        sa.Column('settlement_date', sa.Text(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), sa.ForeignKey('portfolios.id', ondelete='SET NULL')),
        sa.Column('imported_at', sa.Text(), nullable=False),
        sa.Column('raw_memo', sa.Text())
    )


def downgrade() -> None:
    op.drop_table('option_deliveries')
