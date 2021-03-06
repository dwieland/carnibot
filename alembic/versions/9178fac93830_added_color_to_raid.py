"""added color to raid

Revision ID: 9178fac93830
Revises: 65e436e059ab
Create Date: 2018-08-03 09:54:40.010385

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9178fac93830'
down_revision = '65e436e059ab'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('RAID', sa.Column('color', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('RAID', 'color')
    # ### end Alembic commands ###
