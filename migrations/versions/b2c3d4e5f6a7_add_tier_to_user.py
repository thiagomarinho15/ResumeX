"""add tier to user

Revision ID: b2c3d4e5f6a7
Revises: f3c07173fc1c
Create Date: 2026-04-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'f3c07173fc1c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user',
        sa.Column('tier', sa.String(length=20), nullable=False, server_default='standard'),
    )


def downgrade():
    op.drop_column('user', 'tier')
