"""create User_Pending_Confirmation table

Bảng lưu giao dịch AI đang chờ người dùng xác nhận (fallback khi không có Redis).

Revision ID: 7c3e9a1f2b4d
Revises: 310468d6c0a8
Create Date: 2026-10-25 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c3e9a1f2b4d'
down_revision: Union[str, None] = '310468d6c0a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "User_Pending_Confirmation"


def upgrade() -> None:
    # Bỏ qua nếu bảng đã được tạo tay trên một số môi trường
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_key", sa.String(length=120), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("User.user_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("intent", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_User_Pending_Confirmation_session_key", TABLE, ["session_key"], unique=True)
    op.create_index("ix_User_Pending_Confirmation_user_id", TABLE, ["user_id"])
    op.create_index("ix_User_Pending_Confirmation_expires_at", TABLE, ["expires_at"])


def downgrade() -> None:
    op.drop_table(TABLE)
