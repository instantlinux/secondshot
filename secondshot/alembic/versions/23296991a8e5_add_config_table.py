"""add config table

Revision ID: 23296991a8e5
Revises: ab8ec674d281
Create Date: 2018-08-15 11:53:00.857193

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '23296991a8e5'
down_revision = 'ab8ec674d281'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'config',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('host_id', sa.INTEGER(), nullable=False),
        sa.Column('keyword', sa.String(length=32), nullable=False),
        sa.Column('value', sa.String(length=1023), nullable=True),
        sa.Column('created', sa.TIMESTAMP(), server_default=sa.func.now(),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )


def downgrade():
    op.drop_table('config')
