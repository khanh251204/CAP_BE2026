"""create User_Lock_History table

Lịch sử khóa / mở khóa tài khoản (sai mật khẩu nhiều lần, admin khóa, mở bằng email...).

Revision ID: 9f4b2c7d1e3a
Revises: 7c3e9a1f2b4d
Create Date: 2026-10-26 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f4b2c7d1e3a'
down_revision: Union[str, None] = '7c3e9a1f2b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "User_Lock_History"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("User.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("User.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_User_Lock_History_user_id", TABLE, ["user_id"])
    op.create_index("ix_User_Lock_History_created_at", TABLE, ["created_at"])


def downgrade() -> None:
    op.drop_table(TABLE)
