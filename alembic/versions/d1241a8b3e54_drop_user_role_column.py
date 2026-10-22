"""drop_user_role_column

Revision ID: d1241a8b3e54
Revises: b536fd09db83
Create Date: 2026-10-21 10:12:45.426012+07:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1241a8b3e54'
down_revision: Union[str, None] = 'b536fd09db83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Xóa cột role cũ trong bảng User vì đã chuyển sang bảng Role và cột role_id
    op.drop_column('User', 'role')


def downgrade() -> None:
    op.add_column('User', sa.Column('role', sa.String(length=30), nullable=False, server_default='user'))
