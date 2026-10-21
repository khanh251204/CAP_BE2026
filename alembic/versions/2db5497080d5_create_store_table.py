"""create_store_table

Revision ID: 2db5497080d5
Revises: d1241a8b3e54
Create Date: 2026-10-21 10:26:49.287264+07:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2db5497080d5'
down_revision: Union[str, None] = 'd1241a8b3e54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tạo bảng Store riêng biệt
    op.create_table(
        'Store',
        sa.Column('store_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('store_name', sa.String(length=255), nullable=False),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('address_detail', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['User.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('store_id')
    )
    op.create_index(op.f('ix_Store_user_id'), 'Store', ['user_id'], unique=False)

    # 2. Migrate dữ liệu store_name và business_type hiện tại của User sang bảng Store
    op.execute("""
        INSERT INTO `Store` (user_id, store_name, business_type, address_detail, created_at)
        SELECT user_id, 
               IFNULL(NULLIF(store_name, ''), CONCAT('Cửa hàng của ', full_name)), 
               business_type, 
               address_detail, 
               created_at
        FROM `User`
        WHERE store_name IS NOT NULL AND store_name != '' OR account_type = 'business';
    """)

    # 3. Thêm cột store_id vào User để trỏ đến Cửa hàng hiện tại đang làm việc
    op.add_column('User', sa.Column('store_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_user_store_id', 'User', 'Store', ['store_id'], ['store_id'], ondelete='SET NULL')

    # Đồng bộ ngược store_id vào User
    op.execute("""
        UPDATE `User` u
        JOIN `Store` s ON u.user_id = s.user_id
        SET u.store_id = s.store_id;
    """)

    # 4. Xóa cột store_name cũ trong User
    op.drop_column('User', 'store_name')


def downgrade() -> None:
    op.add_column('User', sa.Column('store_name', sa.String(length=255), nullable=True))
    op.execute("""
        UPDATE `User` u
        JOIN `Store` s ON u.store_id = s.store_id
        SET u.store_name = s.store_name;
    """)
    op.drop_constraint('fk_user_store_id', 'User', type_='foreignkey')
    op.drop_column('User', 'store_id')
    op.drop_table('Store')
