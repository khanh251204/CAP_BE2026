from typing import Any


def build_payload(
    intent: str,
    entities: dict[str, Any],
    text: str
) -> dict:

    if intent == "ban_hang":

        return {
            "product_name": entities.get("product"),
            "product_id": entities.get("product_id"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "customer_name": entities.get("customer"),
            "customer_id": entities.get("customer_id"),
            "amount_paid": entities.get("amount_paid"),
            "payment_status": entities.get("payment"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "nhap_hang":
        print("payment_status", entities.get("payment"))

        return {
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "supplier_name": entities.get("supplier"),
            "payment_status": entities.get("payment"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "kiem_kho":

        return {
            "product_name": entities.get("product")
        }

    if intent in ("tim_san_pham", "xem_san_pham"):

        return {
            "name": entities.get("product")
        }

    if intent == "them_san_pham":

        return {
            "name": entities.get("product"),
            "default_unit": entities.get("unit"),
            "unit_price": entities.get("price")
        }

    if intent == "sua_san_pham":

        return {
            "product_name": entities.get("product"),
            "new_product_name": entities.get("new_product_name"),
            "product_id": entities.get("product_id"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "input_text": text
        }

    if intent == "xoa_san_pham":

        return {
            "product_name": entities.get("product"),
            "product_id": entities.get("product_id")
        }

    if intent in ("ghi_no_khach_hang", "khach_ghi_no"):

        return {
            "customer_name": entities.get("customer"),
            "customer_id": entities.get("customer_id"),
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "original_amount": entities.get("original_amount") or entities.get("price"),
            "amount": entities.get("original_amount") or entities.get("price"),
            "transaction_id": entities.get("transaction_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("thu_no_khach_hang", "thu_no_khach"):

        return {
            "customer_name": entities.get("customer"),
            "customer_id": entities.get("customer_id"),
            "account_id": entities.get("account_id"),
            "amount": entities.get("amount") or entities.get("price"),
            "debt_id": entities.get("debt_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("ghi_no_nha_cung_cap", "ncc_ghi_no"):

        return {
            "supplier_name": entities.get("supplier"),
            "supplier_id": entities.get("supplier_id"),
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "original_amount": entities.get("original_amount") or entities.get("amount") or entities.get("price"),
            "amount": entities.get("original_amount") or entities.get("amount") or entities.get("price"),
            "transaction_id": entities.get("transaction_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("thu_no_nha_cung_cap", "tra_no_nha_cung_cap", "tra_no_ncc"):

        return {
            "supplier_name": entities.get("supplier"),
            "supplier_id": entities.get("supplier_id"),
            "account_id": entities.get("account_id"),
            "amount": entities.get("amount") or entities.get("price"),
            "debt_id": entities.get("debt_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "chi_phi":

        return {
            "amount": entities.get("price"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "hang_hong":

        return {
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "amount": entities.get("price"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "bao_cao":

        return {
            "date": entities.get("date"),
            "input_text": text
        }

    return entities
