from datetime import datetime

from sqlalchemy.orm import Session
from app.models.product_model import Product

from sqlalchemy.orm import Session
from sqlalchemy import  func, case
from app.models.inventory_model import InventoryTransaction


def get_products_with_stock(db: Session, user_id: int):
    """
    Lấy thông tin sản phẩm kèm:
    - total_imported: Tổng số lượng đã nhập (type = 'IN')
    - total_sold: Tổng số lượng đã bán/xuất (type = 'OUT')
    - stock_quantity: Số lượng tồn kho hiện tại (lấy quantity_after mới nhất)
    """
    # 1. Subquery lấy quantity_after của giao dịch mới nhất (theo inventory_transaction_id)
    latest_trans_subquery = (
        db.query(
            InventoryTransaction.product_id,
            InventoryTransaction.quantity_after,
            func.row_number().over(
                partition_by=InventoryTransaction.product_id,
                order_by=InventoryTransaction.inventory_transaction_id.desc()
            ).label("rn")
        )
        .filter(InventoryTransaction.user_id == user_id)
        .subquery()
    )

    # 2. Main query: Tính tổng IN, tổng OUT và JOIN với giao dịch mới nhất
    results = (
        db.query(
            Product,
            func.coalesce(
                func.sum(
                    case((InventoryTransaction.inventory_type == 'IN', InventoryTransaction.quantity), else_=0)
                ), 
                0
            ).label("total_imported"),
            func.coalesce(
                func.sum(
                    case((InventoryTransaction.inventory_type == 'OUT', InventoryTransaction.quantity), else_=0)
                ), 
                0
            ).label("total_sold"),
            func.coalesce(latest_trans_subquery.c.quantity_after, 0).label("stock_quantity")
        )
        .outerjoin(
            InventoryTransaction,
            (Product.product_id == InventoryTransaction.product_id)
        )
        .outerjoin(
            latest_trans_subquery,
            (Product.product_id == latest_trans_subquery.c.product_id) & (latest_trans_subquery.c.rn == 1)
        )
        .filter(
            Product.user_id == user_id,
            Product.is_active == True
        )
        .group_by(
            Product.product_id,
            latest_trans_subquery.c.quantity_after
        )
        .all()
    )

    # 3. Format dữ liệu trả về
    data = []
    for product, total_imported, total_sold, stock_quantity in results:
        data.append({
            "product_id": product.product_id,
            "user_id": product.user_id,
            "name": product.product_name,
            "default_unit": product.default_unit,
            "unit_price": float(product.unit_price) if product.unit_price else 0.0,
            "min_quantity": float(product.min_quantity) if product.min_quantity else 0.0,
            "is_active": product.is_active,
            "total_imported": float(total_imported), # Tổng đã nhập
            "total_sold": float(total_sold),         # Tổng sp bán ra (OUT)
            "stock_quantity": float(stock_quantity)  # Tồn kho thực tế (quantity_after gần nhất)
        })

    return data
def get_product_by_name(db: Session, user_id: int, product_name: str):
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.product_name == product_name,
            Product.is_active == True
        )
        .first()
    )


def create_product(
    db: Session,
    user_id: int,
    product_name: str,
    unit: str | None,
    price: float
):
    now = datetime.now()
    product = Product(
        user_id=user_id,
        product_name=product_name,
        default_unit=unit,
        unit_price=str(price),
        is_active=True,
        created_at=now,
        updated_at=now
    )
    db.add(product)
    db.flush()
    return product


def get_product_by_id(db: Session, user_id: int, product_id: int):
    return (
        db.query(Product)
        .filter(
            Product.product_id == product_id,
            Product.user_id == user_id,
            Product.is_active == True
        )
        .first()
    )


def get_all_products(db: Session, user_id: int):
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.is_active == True
        )
        .all()
    )


def search_products_by_name(db: Session, user_id: int, name: str):
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.is_active == True,
            Product.product_name.ilike(f"%{name}%")
        )
        .all()
    )


def get_product_with_lock(db: Session, user_id: int, product_id: int):
    """
    Khóa dòng (row-level lock) để tránh race condition khi cập nhật tồn kho đồng thời.
    """
    return (
        db.query(Product)
        .filter(
            Product.product_id == product_id,
            Product.user_id == user_id,
            Product.is_active == True
        )
        .with_for_update()
        .first()
    )


def update_product(db: Session, product: Product, data: dict):
    if "product_name" in data and data["product_name"] is not None:
        product.product_name = data["product_name"]

    if "default_unit" in data and data["default_unit"] is not None:
        product.default_unit = data["default_unit"]

    if "min_quantity" in data and data["min_quantity"] is not None:
        product.min_quantity = data["min_quantity"]

    if "unit_price" in data and data["unit_price"] is not None:
        product.unit_price = str(data["unit_price"])

    if "is_active" in data and data["is_active"] is not None:
        product.is_active = data["is_active"]

    if "category_id" in data:
        product.category_id = data["category_id"]

    if "img" in data:
        product.img = data["img"]

    product.updated_at = datetime.now()

    db.commit()
    db.refresh(product)

    return product


def soft_delete_product(db: Session, product: Product):
    product.is_active = False
    product.updated_at = datetime.now()

    db.commit()
    db.refresh(product)
    return product


def hard_delete_product(db: Session, product: Product):
    db.delete(product)
    db.commit()
    return True


delete_product = soft_delete_product