from typing import Optional, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.intent_model import Intent

INTENT_ALIASES = {
    "tra_no_nha_cung_cap": [
        "tra_no_nha_cung_cap",
        "tra_no_cung_cap",
        "tra_no_phai_tra",
        "tra_no_ncc",
        "thu_no_nha_cung_cap",
    ],
    "thu_no_khach_hang": [
        "thu_no_khach_hang",
        "thu_no_phai_thu",
        "thu_no_khach",
    ],
    "ghi_no_nha_cung_cap": [
        "ghi_no_nha_cung_cap",
        "ghi_no_cung_cap",
        "ghi_no_phai_tra",
        "ncc_ghi_no",
    ],
    "ghi_no_khach_hang": [
        "ghi_no_khach_hang",
        "ghi_no_phai_thu",
        "khach_ghi_no",
    ],
}


def _get_intent_id(db: Session, intent_name: str, fallback_type: str = "DEBT") -> Optional[int]:
    """
    Tra cứu intent_id theo tên intent và các tên đồng nghĩa (alias).
    """
    intent = (
        db.query(Intent)
        .filter(Intent.intent_name.ilike(intent_name))
        .first()
    )
    if intent:
        return intent.intent_id

    for group_key, aliases in INTENT_ALIASES.items():
        if intent_name.lower() in [a.lower() for a in aliases]:
            for alias in aliases:
                alt_intent = (
                    db.query(Intent)
                    .filter(Intent.intent_name.ilike(alias))
                    .first()
                )
                if alt_intent:
                    return alt_intent.intent_id

    is_payment = any(k in intent_name.lower() for k in ["tra_no", "thu_no", "pay", "collect"])
    query = db.query(Intent).filter(Intent.intent_type == fallback_type)
    if is_payment:
        pay_intent = query.filter(
            or_(
                Intent.intent_name.ilike("%tra_no%"),
                Intent.intent_name.ilike("%thu_no%"),
            )
        ).first()
        if pay_intent:
            return pay_intent.intent_id

    intent = query.first()
    if intent:
        return intent.intent_id

    first_intent = db.query(Intent).first()
    if first_intent:
        return first_intent.intent_id

    return None


class DebtHelperMixin:
    @staticmethod
    def format_debt(result) -> Optional[Dict[str, Any]]:
        if not result:
            return None

        if hasattr(result, "_mapping"):
            debt = result[0]
            customer_name = result._mapping.get("customer_name")
            supplier_name = result._mapping.get("supplier_name")
        elif isinstance(result, (list, tuple)):
            debt = result[0]
            if len(result) > 2:
                customer_name = result[1]
                supplier_name = result[2]
            elif len(result) == 2:
                if getattr(debt, "direction", None) == "PAYABLE" or getattr(debt, "supplier_id", None):
                    customer_name = None
                    supplier_name = result[1]
                else:
                    customer_name = result[1]
                    supplier_name = None
            else:
                customer_name = None
                supplier_name = None
        else:
            debt = result
            customer_name = None
            supplier_name = None

        if customer_name is None:
            customer = getattr(debt, "customer", None)
            customer_name = getattr(customer, "customer_name", None) if customer else None

        if supplier_name is None:
            supplier = getattr(debt, "supplier", None)
            supplier_name = getattr(supplier, "supplier_name", None) if supplier else None

        orig_amt = float(debt.original_amount) if debt.original_amount is not None else 0.0
        rem_debt = float(debt.remaining_debt) if debt.remaining_debt is not None else 0.0

        return {
            "debt_id": debt.debt_id,
            "transaction_id": debt.transaction_id,
            "user_id": debt.user_id,
            "customer_id": debt.customer_id,
            "customer_name": customer_name,
            "supplier_id": debt.supplier_id,
            "supplier_name": supplier_name,
            "direction": debt.direction,
            "original_amount": orig_amt,
            "remaining_debt": rem_debt,
            "total_debt": orig_amt,
            "status": debt.status,
            "created_at": debt.created_at,
            "updated_at": debt.updated_at,
        }
