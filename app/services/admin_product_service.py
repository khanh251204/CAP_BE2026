"""
Admin Product Management — Service Layer

Provides cross-user product listing, search, filtering, server-side pagination,
detailed product view, and status updates for administrators.
"""
from datetime import datetime
from math import ceil
from typing import Optional, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, desc, or_, case

from app.models.product_model import Product
from app.models.user_model import User
from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail
from app.repositories.inventory.inventory_stock_repo import InventoryStockRepository


class AdminProductService:

    @staticmethod
    def list_products(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        product_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        user_id: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict:
        # === Base query ===
        stmt = select(Product).options(joinedload(Product.user))
        count_stmt = select(func.count()).select_from(Product)

        user_joined = False

        # === Filter: user_id ===
        if user_id is not None:
            stmt = stmt.filter(Product.user_id == user_id)
            count_stmt = count_stmt.filter(Product.user_id == user_id)

        # === Filter: product_type ===
        if product_type:
            pt_val = product_type.strip().upper()
            stmt = stmt.filter(func.upper(Product.product_type) == pt_val)
            count_stmt = count_stmt.filter(func.upper(Product.product_type) == pt_val)

        # === Filter: is_active ===
        if is_active is not None:
            stmt = stmt.filter(Product.is_active == is_active)
            count_stmt = count_stmt.filter(Product.is_active == is_active)

        # === Search: product_name, owner full_name, email, store_name ===
        if search:
            term = search.strip()
            search_conditions = [
                Product.product_name.ilike(f"%{term}%"),
            ]
            if not user_joined:
                stmt = stmt.join(Product.user, isouter=True)
                count_stmt = count_stmt.join(User, Product.user_id == User.user_id, isouter=True)
                user_joined = True

            from app.models.store_model import Store
            search_conditions.extend([
                User.full_name.ilike(f"%{term}%"),
                User.email.ilike(f"%{term}%"),
                User.store_rel.has(Store.store_name.ilike(f"%{term}%")),
            ])
            stmt = stmt.filter(or_(*search_conditions))
            count_stmt = count_stmt.filter(or_(*search_conditions))

        # === Count total ===
        total = db.scalar(count_stmt) or 0

        # === Sorting ===
        if sort_by in ("owner_name", "user_name", "store_name") and not user_joined:
            stmt = stmt.join(Product.user, isouter=True)
            count_stmt = count_stmt.join(User, Product.user_id == User.user_id, isouter=True)
            user_joined = True

        sort_col = _resolve_sort_column(sort_by)
        order_fn = desc if sort_order.lower() == "desc" else lambda c: c.asc()
        stmt = stmt.order_by(order_fn(sort_col), desc(Product.product_id))

        # === Pagination ===
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        products = db.scalars(stmt).unique().all()
        total_pages = ceil(total / limit) if limit > 0 else 0

        # === Serialize items with stock calculation ===
        inv_repo = InventoryStockRepository(db)
        items = []
        for p in products:
            user_obj = p.user
            if user_obj is None and p.user_id:
                user_obj = db.query(User).filter(User.user_id == p.user_id).first()
            stock = float(inv_repo.get_latest_stock(user_id=p.user_id, product_id=p.product_id))
            items.append(_serialize_product_item(p, stock_quantity=stock, user=user_obj))

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        }

    @staticmethod
    def get_product_detail(
        db: Session,
        product_id: int,
    ) -> Dict:
        stmt = (
            select(Product)
            .options(joinedload(Product.user))
            .filter(Product.product_id == product_id)
        )
        product = db.scalars(stmt).unique().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy sản phẩm với ID {product_id}"
            )

        inv_repo = InventoryStockRepository(db)
        stock_quantity = float(inv_repo.get_latest_stock(user_id=product.user_id, product_id=product_id))

        # Totals from InventoryTransaction
        totals_query = (
            db.query(
                func.coalesce(func.sum(case((InventoryTransaction.inventory_type == 'IN', InventoryTransaction.quantity), else_=0)), 0).label("imported"),
                func.coalesce(func.sum(case((InventoryTransaction.inventory_type == 'OUT', InventoryTransaction.quantity), else_=0)), 0).label("sold")
            )
            .filter(InventoryTransaction.product_id == product_id)
            .first()
        )
        total_imported = float(totals_query[0]) if totals_query else 0.0
        total_sold = float(totals_query[1]) if totals_query else 0.0

        # Detail count from TransactionDetail
        tx_count = (
            db.query(func.count(TransactionDetail.detail_id))
            .filter(TransactionDetail.product_id == product_id)
            .scalar() or 0
        )

        user_obj = product.user
        if user_obj is None and product.user_id:
            user_obj = db.query(User).filter(User.user_id == product.user_id).first()

        data = _serialize_product_item(product, stock_quantity=stock_quantity, user=user_obj)
        data.update({
            "total_imported": total_imported,
            "total_sold": total_sold,
            "transaction_count": tx_count,
        })
        return data

    @staticmethod
    def update_product_status(
        db: Session,
        product_id: int,
        is_active: bool,
    ) -> Dict:
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy sản phẩm với ID {product_id}"
            )

        # Bật lại sản phẩm đã ngừng kinh doanh: không được trùng tên với sản phẩm đang bán của cùng user
        if is_active and not product.is_active:
            from app.services.duplicate_guard import ensure_unique_product
            ensure_unique_product(db, product.user_id, product.product_name, exclude_id=product.product_id)

        product.is_active = is_active
        product.updated_at = datetime.now()

        db.commit()
        db.refresh(product)

        status_str = "kích hoạt" if is_active else "ngừng kinh doanh"
        return {
            "success": True,
            "message": f"Đã {status_str} sản phẩm thành công",
            "product_id": product_id,
            "is_active": product.is_active,
        }


# ========================================
# Helper Functions
# ========================================

def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _serialize_user(user: Optional[User]) -> Optional[Dict]:
    if not user:
        return None
    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "store_name": user.store_name,
        "business_type": user.business_type,
        "role": user.role,
    }


def _serialize_product_item(p: Product, stock_quantity: float = 0.0, user: Optional[User] = None) -> Dict:
    owner_obj = user if user is not None else getattr(p, "user", None)
    owner_dict = _serialize_user(owner_obj)

    owner_name = owner_dict["full_name"] if owner_dict else None
    owner_email = owner_dict["email"] if owner_dict else None
    owner_phone = owner_dict["phone_number"] if owner_dict else None
    store_name = owner_dict["store_name"] if owner_dict else None
    business_type = owner_dict["business_type"] if owner_dict else None

    return {
        "product_id": p.product_id,
        "user_id": p.user_id,
        "user": owner_dict,
        "owner": owner_dict,
        "owner_name": owner_name,
        "user_name": owner_name,
        "owner_email": owner_email,
        "owner_phone": owner_phone,
        "store_name": store_name,
        "business_type": business_type,
        "product_name": p.product_name,
        "product_type": str(getattr(p, "product_type", "RESALE")),
        "img": p.img,
        "default_unit": p.default_unit,
        "unit_price": _safe_float(p.unit_price),
        "min_quantity": _safe_float(p.min_quantity),
        "is_active": p.is_active,
        "stock_quantity": stock_quantity,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _resolve_sort_column(sort_by: str):
    mapping = {
        "created_at": Product.created_at,
        "product_name": Product.product_name,
        "unit_price": Product.unit_price,
        "product_id": Product.product_id,
        "owner_name": User.full_name,
        "user_name": User.full_name,
        "store_name": User.store_name,
    }
    return mapping.get(sort_by, Product.created_at)
