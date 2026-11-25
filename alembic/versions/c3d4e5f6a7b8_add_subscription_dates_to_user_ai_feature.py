"""add subscription dates to User_AI_Feature

Lưu ngày đăng ký (subscribed_at), ngày hết hạn (expires_at) và mốc đã gửi email nhắc
sắp hết hạn (expiry_reminded_at) cho gói AI đăng ký theo tháng.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-11-22 03:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "User_AI_Feature"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(TABLE)}
    if "subscribed_at" not in cols:
        op.add_column(TABLE, sa.Column("subscribed_at", sa.DateTime(), nullable=True))
    if "expires_at" not in cols:
        op.add_column(TABLE, sa.Column("expires_at", sa.DateTime(), nullable=True))
        op.create_index("ix_user_ai_feature_expires_at", TABLE, ["expires_at"])
    if "expiry_reminded_at" not in cols:
        op.add_column(TABLE, sa.Column("expiry_reminded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(TABLE)}
    if "expiry_reminded_at" in cols:
        op.drop_column(TABLE, "expiry_reminded_at")
    if "expires_at" in cols:
        try:
            op.drop_index("ix_user_ai_feature_expires_at", table_name=TABLE)
        except Exception:
            pass
        op.drop_column(TABLE, "expires_at")
    if "subscribed_at" in cols:
        op.drop_column(TABLE, "subscribed_at")
