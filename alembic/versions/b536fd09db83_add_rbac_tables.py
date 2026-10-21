"""add_rbac_tables

Revision ID: b536fd09db83
Revises: 
Create Date: 2026-10-21 09:55:58.504501+07:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b536fd09db83'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tạo bảng Role
    op.create_table(
        'Role',
        sa.Column('role_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('role_id')
    )
    op.create_index(op.f('ix_Role_role_name'), 'Role', ['role_name'], unique=True)

    # 2. Tạo bảng Permission
    op.create_table(
        'Permission',
        sa.Column('permission_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('permission_id')
    )
    op.create_index(op.f('ix_Permission_code'), 'Permission', ['code'], unique=True)
    op.create_index(op.f('ix_Permission_module'), 'Permission', ['module'], unique=False)

    # 3. Tạo bảng trung gian Role_Permission
    op.create_table(
        'Role_Permission',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['Permission.permission_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['Role.role_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    # 4. Thêm cột role_id vào bảng User
    op.add_column('User', sa.Column('role_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_user_role_id', 'User', 'Role', ['role_id'], ['role_id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_user_role_id', 'User', type_='foreignkey')
    op.drop_column('User', 'role_id')
    op.drop_table('Role_Permission')
    op.drop_index(op.f('ix_Permission_module'), table_name='Permission')
    op.drop_index(op.f('ix_Permission_code'), table_name='Permission')
    op.drop_table('Permission')
    op.drop_index(op.f('ix_Role_role_name'), table_name='Role')
    op.drop_table('Role')
