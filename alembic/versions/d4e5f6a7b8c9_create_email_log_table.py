"""create Email_Log table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-22 03:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "Email_Log" not in inspector.get_table_names():
        op.create_table(
            "Email_Log",
            sa.Column("email_log_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("to_email", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("email_type", sa.String(length=50), nullable=False, server_default="OTHER"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="SENT"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("text_body", sa.Text(), nullable=True),
            sa.Column("html_body", sa.Text(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("sent_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("email_log_id"),
        )
        op.create_index("ix_Email_Log_email_log_id", "Email_Log", ["email_log_id"])
        op.create_index("ix_Email_Log_to_email", "Email_Log", ["to_email"])
        op.create_index("ix_Email_Log_email_type", "Email_Log", ["email_type"])
        op.create_index("ix_Email_Log_status", "Email_Log", ["status"])
        op.create_index("ix_Email_Log_user_id", "Email_Log", ["user_id"])
        op.create_index("ix_Email_Log_created_at", "Email_Log", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "Email_Log" in inspector.get_table_names():
        op.drop_table("Email_Log")
