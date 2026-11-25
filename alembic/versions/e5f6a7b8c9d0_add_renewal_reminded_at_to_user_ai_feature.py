"""add renewal_reminded_at to User_AI_Feature

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-22 03:38:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "User_AI_Feature" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("User_AI_Feature")}
        if "renewal_reminded_at" not in cols:
            op.add_column("User_AI_Feature", sa.Column("renewal_reminded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "User_AI_Feature" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("User_AI_Feature")}
        if "renewal_reminded_at" in cols:
            op.drop_column("User_AI_Feature", "renewal_reminded_at")
