import unicodedata
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def remove_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def parse_nlp_date(nlp_date: Optional[str]) -> datetime:
    transaction_date = datetime.now()
    if nlp_date:
        date_text = str(nlp_date).lower().strip()
        if "hôm qua" in date_text:
            transaction_date = datetime.now() - timedelta(days=1)
        elif "hôm kia" in date_text:
            transaction_date = datetime.now() - timedelta(days=2)
        elif "ngày mai" in date_text:
            transaction_date = datetime.now() + timedelta(days=1)
        else:
            try:
                transaction_date = datetime.fromisoformat(date_text[:10])
            except Exception:
                pass
    return transaction_date


def determine_account_type(payment_method: Optional[str]) -> str:
    acc_type = "CASH"
    if payment_method:
        payment_lower = str(payment_method).lower().strip()
        if "tiền mặt" in payment_lower:
            acc_type = "CASH"
        elif "chuyển khoản" in payment_lower or "ngân hàng" in payment_lower:
            acc_type = "BANK"
        elif "momo" in payment_lower or "ví" in payment_lower or "zalopay" in payment_lower:
            acc_type = "E-WALLET"
    return acc_type


def validate_groq_intent_entities(groq_intent: str, entities: Dict[str, Any]):
    product_name = entities.get("product")
    quantity = entities.get("quantity")
    price = entities.get("price")
    customer_name = entities.get("customer")
    supplier_name = entities.get("supplier")

    if groq_intent == "ban_hang":
        if not product_name or not quantity or not price:
            raise ValueError("Bán hàng phải có product, quantity, price")
    elif groq_intent in {"nhap_hang", "mua_hang"}:
        if not product_name or not quantity or not price:
            raise ValueError("Nhập hàng phải có product, quantity, price")
    elif groq_intent in {"thu_tien", "thu_no_phai_thu", "thu_no_khach_hang", "chi_tien"}:
        if not price:
            raise ValueError("Giao dịch tiền phải có amount")
    elif groq_intent in {"tra_no_phai_tra", "tra_no_nha_cung_cap"}:
        if not supplier_name or not price:
            raise ValueError("Trả nợ nhà cung cấp phải có supplier và price")
    elif groq_intent in {"ghi_no_phai_thu", "ghi_no_khach_hang"}:
        if not price or not customer_name:
            raise ValueError("Ghi nợ phải thu phải có customer và amount")
    elif groq_intent in {"ghi_no_phai_tra", "ghi_no_nha_cung_cap"}:
        if not price or not supplier_name:
            raise ValueError("Ghi nợ phải trả phải có supplier và amount")
