"""switch to bge-small model with 384 dimensions

Revision ID: 13ab4ac6ea89
Revises: 04b68bac8d84
Create Date: 2026-10-25 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy  # <-- Added this missing import

# revision identifiers, used by Alembic.
revision: str = '13ab4ac6ea89'
down_revision: Union[str, None] = '04b68bac8d84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # We must truncate chunks first because you cannot automatically 
    # cast a 768-dim vector to a 384-dim vector in Postgres.
    op.execute("TRUNCATE TABLE chunks CASCADE;")
    
    op.alter_column('chunks', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=768),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               existing_nullable=False)


def downgrade() -> None:
    op.execute("TRUNCATE TABLE chunks CASCADE;")
    
    op.alter_column('chunks', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=768),
               existing_nullable=False)