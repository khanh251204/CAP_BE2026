"""drop_user_address_detail_column

Revision ID: 310468d6c0a8
Revises: 2db5497080d5
Create Date: 2026-10-21 10:44:07.131779+07:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '310468d6c0a8'
down_revision: Union[str, None] = '2db5497080d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Xóa cột address_detail khỏi User vì đã được chuyển sang bảng Store
    op.drop_column('User', 'address_detail')


def downgrade() -> None:
    op.add_column('User', sa.Column('address_detail', sa.String(length=255), nullable=True))
