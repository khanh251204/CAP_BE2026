from datetime import datetime

from sqlalchemy.orm import Session
from app.models.product_model import Product

from sqlalchemy.orm import Session
from sqlalchemy import  func, case
from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.transaction_model import Transaction


def get_last_import_prices(db: Session, user_id: int) -> dict:
    """
    Giá nhập gần nhất của từng sản phẩm: đơn giá trên dòng hàng của lần nhập kho (IN) mới nhất
    có gắn giao dịch mua hàng. Bỏ qua IN do khách trả hàng (giao dịch có khách hàng) và
    nhập kho thủ công / kiểm kê (không có giao dịch nên không có giá).
    Trả về {product_id: unit_price}.
    """
    ranked = (
        db.query(
            InventoryTransaction.product_id.label("product_id"),
            TransactionDetail.unit_price.label("unit_price"),
            func.row_number().over(
                partition_by=InventoryTransaction.product_id,
                order_by=InventoryTransaction.inventory_transaction_id.desc(),
            ).label("rn"),
        )
        .join(
            TransactionDetail,
            (TransactionDetail.transaction_id == InventoryTransaction.transaction_id)
            & (TransactionDetail.product_id == InventoryTransaction.product_id),
        )
        .join(Transaction, Transaction.transaction_id == InventoryTransaction.transaction_id)
        .filter(
            InventoryTransaction.user_id == user_id,
            InventoryTransaction.inventory_type == "IN",
            Transaction.customer_id.is_(None),
            TransactionDetail.unit_price > 0,
        )
        .subquery()
    )
    rows = db.query(ranked.c.product_id, ranked.c.unit_price).filter(ranked.c.rn == 1).all()
    return {pid: float(price) for pid, price in rows}


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
    import_prices = get_last_import_prices(db, user_id)
    from app.services.product_unit_service import units_by_product
    units_map = units_by_product(db, user_id, [row[0].product_id for row in results])
    data = []
    for product, total_imported, total_sold, stock_quantity in results:
        data.append({
            "product_id": product.product_id,
            "user_id": product.user_id,
            "name": product.product_name,
            "default_unit": product.default_unit,
            "product_type": getattr(product, "product_type", "RESALE"),
            "unit_price": float(product.unit_price) if product.unit_price else 0.0,
            # Giá nhập gần nhất (null nếu chưa từng nhập qua giao dịch mua hàng)
            "last_import_price": import_prices.get(product.product_id),
            "min_quantity": float(product.min_quantity) if product.min_quantity else 0.0,
            "is_active": product.is_active,
            "total_imported": float(total_imported), # Tổng đã nhập
            "total_sold": float(total_sold),         # Tổng sp bán ra (OUT)
            "stock_quantity": float(stock_quantity),  # Tồn kho thực tế (quantity_after gần nhất)
            # Đơn vị quy đổi riêng: [{"unit_name": "gói", "factor": 1000}] = 1 gói bằng 1000 default_unit
            "units": units_map.get(product.product_id, []),
        })

    return data
def get_product_by_name(db: Session, user_id: int, product_name: str):
    clean_name = product_name.strip() if product_name else ""
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.product_name.ilike(clean_name),
            Product.is_active == True
        )
        .order_by(Product.product_id.asc())
        .first()
    )


def create_product(
    db: Session,
    user_id: int,
    product_name: str,
    unit: str | None,
    price: float,
    product_type: str | None = "RESALE"
):
    now = datetime.now()
    product = Product(
        user_id=user_id,
        product_name=product_name,
        default_unit=unit,
        unit_price=str(price),
        product_type=product_type or "RESALE",
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

    if "product_type" in data and data["product_type"] is not None:
        product.product_type = str(data["product_type"])

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
