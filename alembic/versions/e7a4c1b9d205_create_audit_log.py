"""create Audit_Log table

Vết kiểm toán thay đổi giao dịch (tạo / sửa / xoá), ghi tự động bằng sự kiện ORM.

Revision ID: e7a4c1b9d205
Revises: a3b8e5d2c917
Create Date: 2026-11-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a4c1b9d205'
down_revision: Union[str, None] = 'a3b8e5d2c917'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "Audit_Log"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=10), nullable=False, server_default="SYSTEM"),
        sa.Column("source", sa.String(length=20), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("api_path", sa.String(length=255), nullable=True),
        sa.Column("http_method", sa.String(length=10), nullable=True),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
    )
    op.create_index("ix_Audit_Log_id", TABLE, ["id"])
    op.create_index("ix_Audit_Log_created_at", TABLE, ["created_at"])
    op.create_index("ix_Audit_Log_entity_type", TABLE, ["entity_type"])
    op.create_index("ix_Audit_Log_transaction_id", TABLE, ["transaction_id"])
    op.create_index("ix_Audit_Log_action", TABLE, ["action"])
    op.create_index("ix_Audit_Log_owner_user_id", TABLE, ["owner_user_id"])
    op.create_index("ix_Audit_Log_actor_user_id", TABLE, ["actor_user_id"])
    op.create_index("ix_Audit_Log_request_id", TABLE, ["request_id"])
    op.create_index("ix_audit_log_tx_created", TABLE, ["transaction_id", "created_at"])


def downgrade() -> None:
    op.drop_table(TABLE)
