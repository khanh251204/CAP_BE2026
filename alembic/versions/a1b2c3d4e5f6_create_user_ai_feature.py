"""create User_AI_Feature table

Quản lý gói AI & danh sách intent / tính năng (multi-item, OCR) được phép cho từng tài khoản,
đồng thời hỗ trợ rút gọn system prompt động theo gói để giảm token và độ trễ trên production.

Revision ID: a1b2c3d4e5f6
Revises: e9f3a1b2c4d5
Create Date: 2026-11-22 01:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e9f3a1b2c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "User_AI_Feature"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE in inspector.get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("User.user_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("plan_code", sa.String(64), nullable=True),
        sa.Column("allowed_intents", sa.JSON(), nullable=True),
        sa.Column("allow_multi_item", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("allow_ocr", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_user_ai_feature_plan_code", TABLE, ["plan_code"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    op.drop_index("ix_user_ai_feature_plan_code", table_name=TABLE)
    op.drop_table(TABLE)
