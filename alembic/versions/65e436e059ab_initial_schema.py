"""Initial schema

Revision ID: 65e436e059ab
Revises: 
Create Date: 2018-08-01 12:48:48.596569

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65e436e059ab'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'RAID',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=True),
        sa.Column('message_id', sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date')
    )
    op.create_table(
        'RAID_USER_REACTION',
        sa.Column('raid_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=False),
        sa.Column('reaction', sa.String(length=32), nullable=True),
        sa.Column('reason', sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint('raid_id', 'user_id', 'at')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('RAID_USER_REACTION')
    op.drop_table('RAID')
    # ### end Alembic commands ###
