"""
Debt Service — Quản lý công nợ khách hàng & nhà cung cấp theo ERD.

Cung cấp các chức năng chính:
  - create_customer_debt  (POST /debts/customer)              -> Ghi nợ khách hàng (intent: ghi_no_khach_hang)
  - collect_customer_debt (POST /debts/customer/{debt_id}/payments hoặc /debts/customer/payments) -> Thu tiền nợ khách hàng (intent: thu_no_khach_hang)
  - get_customer_debts    (GET /debts/customer)               -> Danh sách công nợ khách hàng
  - create_supplier_debt  (POST /debts/supplier)              -> Ghi nợ nhà cung cấp (intent: ghi_no_nha_cung_cap)
  - pay_supplier_debt     (POST /debts/supplier/{debt_id}/payments hoặc /debts/supplier/payments) -> Trả nợ NCC (intent: thu_no_nha_cung_cap / tra_no_nha_cung_cap)
  - get_supplier_debts    (GET /debts/supplier)               -> Danh sách công nợ nhà cung cấp
  - get_all_debts         (GET /debts/)                       -> Danh sách toàn bộ công nợ
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.account_model import Account
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.intent_model import Intent
from app.repositories.debt_repository import DebtRepository


# =========================================================
# Helper: lấy intent_id an toàn từ database
# =========================================================
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
    Tránh fallback bừa bãi sang intent khác loại (ví dụ trả nợ bị nhầm thành ghi nợ).
    """
    # 1. Tìm chính xác theo intent_name
    intent = (
        db.query(Intent)
        .filter(Intent.intent_name.ilike(intent_name))
        .first()
    )
    if intent:
        return intent.intent_id

    # 2. Tìm qua danh sách alias tương ứng
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

    # 3. Fallback theo intent_type (ưu tiên intent không phải 'ghi_no' nếu đang tìm tra_no/thu_no)
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

    # 4. Fallback lấy bất kỳ intent nào nếu có
    first_intent = db.query(Intent).first()
    if first_intent:
        return first_intent.intent_id

    return None


class DebtService:

    # =====================================================
    # 1. TẠO CÔNG NỢ KHÁCH HÀNG (GHI NỢ KHÁCH HÀNG)
    # Intent: ghi_no_khach_hang (create_customer_debt)
    # =====================================================
    @staticmethod
    def create_customer_debt(
        db: Session,
        user_id: int,
        customer_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tạo công nợ khách hàng.
        - customer_id: ID khách hàng
        - total_debt: Số tiền nợ ban đầu (original_amount)
        - transaction_id: Transaction nguồn từ bán hàng (nếu có); nếu không truyền, server tự tạo Transaction loại ghi nợ
        - note: Ghi chú
        """
        # 1. Kiểm tra khách hàng thuộc user
        customer = DebtRepository.get_customer_by_id_and_user(
            customer_id=customer_id,
            user_id=user_id,
            db=db
        )

        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        # 2. Validate số tiền nợ
        total_debt_dec = Decimal(str(total_debt))
        if total_debt_dec <= 0:
            raise HTTPException(
                status_code=400,
                detail="Số tiền công nợ phải lớn hơn 0"
            )

        try:
            # 3. Nếu chưa có transaction_id -> tự động tạo Transaction rỗng loại ghi nợ
            if transaction_id is None:
                intent_id = _get_intent_id(db, "ghi_no_khach_hang")

                new_tx = Transaction(
                    user_id=user_id,
                    intent_id=intent_id,
                    account_id=None,
                    customer_id=customer_id,
                    supplier_id=None,
                    total_amount=total_debt_dec,
                    payment_status="PENDING",  # Đúng chuẩn enum ERD: 'PAID', 'PARTIAL', 'PENDING'
                    input_method="MANUAL",
                    input_text=note or "Ghi nợ khách hàng",
                    transaction_date=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                db.add(new_tx)
                db.flush()
                transaction_id = new_tx.transaction_id

            # 4. Tạo bản ghi Debt theo chuẩn ERD
            debt = Debt(
                transaction_id=transaction_id,
                user_id=user_id,
                customer_id=customer_id,
                supplier_id=None,
                direction="RECEIVABLE",       # Khách nợ mình -> RECEIVABLE
                original_amount=total_debt_dec,
                remaining_debt=total_debt_dec,
                status="UNPAID",              # Đúng chuẩn enum ERD: 'UNPAID', 'PARTIAL', 'PAID'
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            db.add(debt)
            db.commit()
            db.refresh(debt)

            return {
                "debt_id": debt.debt_id,
                "status": debt.status,
                "total_debt": float(debt.original_amount),
                "original_amount": float(debt.original_amount),
                "remaining_debt": float(debt.remaining_debt),
            }

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi tạo công nợ khách hàng: {str(e)}"
            )

    # =====================================================
    # 2. THU TIỀN CÔNG NỢ KHÁCH HÀNG (THU NỢ KHÁCH HÀNG)
    # Intent: thu_no_khach_hang (collect_customer_debt)
    #
    # HỖ TRỢ 2 CHẾ ĐỘ:
    #   a) Trả đích danh 1 khoản nợ  -> truyền debt_id (giữ nguyên hành vi cũ)
    #   b) Trả theo khách hàng, tự  -> truyền customer_id (KHÔNG truyền debt_id)
    #      động phân bổ FIFO qua       Server tự tìm mọi Debt đang mở của
    #      nhiều khoản nợ đang mở      customer đó, trả từ khoản CŨ NHẤT
    #                                  (created_at tăng dần) trước, hết khoản
    #                                  này mới sang khoản kế tiếp.
    #
    # Chỉ cần truyền MỘT trong hai: debt_id HOẶC customer_id.
    # =====================================================
    @staticmethod
    def collect_customer_debt(
        db: Session,
        user_id: int,
        account_id: int,
        amount: float,
        debt_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Thu tiền từ khách hàng đang có nợ.

        Chế độ 1 - debt_id: thu đích danh cho 1 khoản nợ.
        Chế độ 2 - customer_id: thu một khoản tiền tổng, tự động phân bổ FIFO
                   (khoản nợ cũ nhất trả trước) qua tất cả Debt đang mở
                   (status IN ('UNPAID','PARTIAL'), direction='RECEIVABLE')
                   của khách hàng đó, cho tới khi hết tiền hoặc hết nợ.
        """
        if payment_date is None:
            payment_date = datetime.now()

        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise HTTPException(
                status_code=400,
                detail="Số tiền thu phải lớn hơn 0"
            )

        if not debt_id and not customer_id:
            raise HTTPException(
                status_code=400,
                detail="Phải truyền debt_id (thu 1 khoản cụ thể) hoặc customer_id (thu tổng, tự phân bổ FIFO)"
            )

        try:
            # ---------------------------------------------------------
            # Bước 1: xác định danh sách Debt sẽ thu
            # ---------------------------------------------------------
            if debt_id:
                # Chế độ 1: 1 khoản nợ cụ thể
                debt = DebtRepository.get_debt_by_id_and_user(
                    debt_id=debt_id,
                    user_id=user_id,
                    db=db,
                    direction="RECEIVABLE",
                    for_update=True
                )
                if not debt:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc về bạn"
                    )
                if str(debt.status).upper() == "PAID" or (debt.remaining_debt is not None and Decimal(str(debt.remaining_debt)) <= Decimal("0")):
                    raise HTTPException(
                        status_code=400,
                        detail="Công nợ này đã được thanh toán đầy đủ"
                    )
                debts_to_pay = [debt]
            else:
                # Chế độ 2: FIFO theo customer_id
                customer = DebtRepository.get_customer_by_id_and_user(
                    customer_id=customer_id,
                    user_id=user_id,
                    db=db
                )
                if not customer:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý"
                    )

                debts_to_pay = DebtRepository.get_open_debts_by_customer_and_user(
                    db=db,
                    customer_id=customer_id,
                    user_id=user_id,
                    direction="RECEIVABLE",
                    order_by="created_at asc",
                    for_update=True
                )
                if not debts_to_pay:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Khách hàng {customer_id} hiện không có khoản nợ nào đang mở"
                    )

            # ---------------------------------------------------------
            # Bước 2: validate tổng tiền thu so với TỔNG nợ còn lại
            # ---------------------------------------------------------
            remaining_map = {}
            total_remaining = Decimal("0")
            for d in debts_to_pay:
                r = Decimal(str(d.remaining_debt)) if d.remaining_debt is not None else Decimal(str(d.original_amount or 0))
                remaining_map[d.debt_id] = r
                total_remaining += r

            if total_remaining <= Decimal("0"):
                raise HTTPException(
                    status_code=400,
                    detail="Các khoản công nợ này đã được thanh toán đầy đủ"
                )

            if amount_dec > total_remaining:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Số tiền thu ({amount_dec}) vượt quá tổng số nợ hiện có "
                        f"({total_remaining}). Vui lòng nhập số tiền nhỏ hơn hoặc bằng {total_remaining}."
                    )
                )

            # ---------------------------------------------------------
            # Bước 3: kiểm tra tài khoản nhận tiền
            # ---------------------------------------------------------
            account = DebtRepository.get_account_by_id_and_user(
                account_id=account_id,
                user_id=user_id,
                db=db,
                for_update=True
            )
            if not account:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa"
                )

            intent_id = _get_intent_id(db, "thu_no_khach_hang")

            # ---------------------------------------------------------
            # Bước 4: tạo 1 Transaction duy nhất cho cả lượt thu
            # ---------------------------------------------------------
            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=customer_id if customer_id else debts_to_pay[0].customer_id,
                supplier_id=None,
                total_amount=amount_dec,
                payment_status="PAID",       # Tiền thu ngay -> PAID
                input_method="MANUAL",
                input_text=note or "Thu nợ khách hàng",
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            # ---------------------------------------------------------
            # Bước 5: phân bổ FIFO qua từng Debt
            # ---------------------------------------------------------
            amount_left = amount_dec
            payments_created = []
            debts_summary = []

            for d in debts_to_pay:
                if amount_left <= Decimal("0"):
                    break

                remaining_before = remaining_map[d.debt_id]
                if remaining_before <= Decimal("0"):
                    continue

                allocated = min(amount_left, remaining_before)

                orig_amount = Decimal(str(d.original_amount)) if d.original_amount else allocated
                payment_percentage = (
                    (allocated / orig_amount * 100).quantize(Decimal("0.01"))
                    if orig_amount > 0 else Decimal("0.00")
                )

                debt_payment = DebtPayment(
                    debt_id=d.debt_id,
                    transaction_id=new_tx.transaction_id,
                    account_id=account_id,
                    amount=allocated,
                    payment_percentage=payment_percentage,
                    payment_date=payment_date,
                    note=note,
                    created_at=datetime.now(),
                )
                db.add(debt_payment)
                db.flush()
                payments_created.append(debt_payment)

                remaining_after = remaining_before - allocated
                if remaining_after <= Decimal("0"):
                    d.remaining_debt = Decimal("0.00")
                    d.status = "PAID"
                else:
                    d.remaining_debt = remaining_after
                    d.status = "PARTIAL"
                d.updated_at = datetime.now()

                # Cập nhật Transaction gốc tương ứng nếu có
                if getattr(d, "transaction", None):
                    d.transaction.payment_status = d.status
                    d.transaction.updated_at = datetime.now()

                debts_summary.append({
                    "debt_id": d.debt_id,
                    "payment_id": debt_payment.payment_id,
                    "amount_applied": float(allocated),
                    "remaining_debt": float(max(d.remaining_debt, Decimal("0"))),
                    "debt_status": d.status,
                })

                amount_left -= allocated

            # ---------------------------------------------------------
            # Bước 6: cộng tiền vào tài khoản
            # ---------------------------------------------------------
            current_balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
            account.balance = current_balance + amount_dec
            account.updated_at = datetime.now()

            db.commit()
            for p in payments_created:
                db.refresh(p)

            # ---------------------------------------------------------
            # Bước 7: trả kết quả
            # ---------------------------------------------------------
            if debt_id:
                d = debts_to_pay[0]
                return {
                    "payment_id": payments_created[0].payment_id if payments_created else None,
                    "debt_id": d.debt_id,
                    "remaining_debt": float(max(d.remaining_debt, Decimal("0"))),
                    "debt_status": d.status,
                    "amount_collected": float(amount_dec),
                }

            remaining_final = max(total_remaining - amount_dec, Decimal("0"))
            return {
                "customer_id": customer_id,
                "payment_id": payments_created[0].payment_id if payments_created else None,
                "amount_collected": float(amount_dec),
                "total_remaining_before": float(total_remaining),
                "total_remaining_after": float(remaining_final),
                "remaining_debt": float(remaining_final),
                "debt_status": "PAID" if remaining_final <= Decimal("0") else "PARTIAL",
                "debts": debts_summary,
            }

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi thu công nợ: {str(e)}"
            )

    # =====================================================
    # 3. LẤY DANH SÁCH CÔNG NỢ KHÁCH HÀNG (RECEIVABLE)
    # =====================================================
    @staticmethod
    def get_customer_debts(
        user_id: int,
        db: Session,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = DebtRepository.get_customer_debts(
            user_id=user_id,
            db=db,
            customer_id=customer_id,
            status=status,
            search=search
        )

        return [
            DebtService.format_debt(result)
            for result in results
        ]

    # =====================================================
    # 4. TẠO CÔNG NỢ NHÀ CUNG CẤP (GHI NỢ NHÀ CUNG CẤP)
    # Intent: ghi_no_nha_cung_cap (create_supplier_debt)
    # =====================================================
    @staticmethod
    def create_supplier_debt(
        db: Session,
        user_id: int,
        supplier_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tạo công nợ nhà cung cấp (nợ phải trả - PAYABLE).
        - supplier_id: ID nhà cung cấp
        - total_debt: Số tiền nợ ban đầu (original_amount)
        - transaction_id: Transaction nguồn từ nhập hàng (nếu có); nếu không truyền, server tự tạo Transaction loại ghi nợ
        - note: Ghi chú
        """
        # 1. Kiểm tra nhà cung cấp thuộc user
        supplier = DebtRepository.get_supplier_by_id_and_user(
            supplier_id=supplier_id,
            user_id=user_id,
            db=db
        )

        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        # 2. Validate số tiền nợ
        total_debt_dec = Decimal(str(total_debt))
        if total_debt_dec <= 0:
            raise HTTPException(
                status_code=400,
                detail="Số tiền công nợ phải lớn hơn 0"
            )

        try:
            # 3. Nếu chưa có transaction_id -> tự động tạo Transaction rỗng loại ghi nợ
            if transaction_id is None:
                intent_id = _get_intent_id(db, "ghi_no_nha_cung_cap")

                new_tx = Transaction(
                    user_id=user_id,
                    intent_id=intent_id,
                    account_id=None,
                    customer_id=None,
                    supplier_id=supplier_id,
                    total_amount=total_debt_dec,
                    payment_status="PENDING",  # Đúng chuẩn enum ERD: 'PAID', 'PARTIAL', 'PENDING'
                    input_method="MANUAL",
                    input_text=note or "Ghi nợ nhà cung cấp",
                    transaction_date=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                db.add(new_tx)
                db.flush()
                transaction_id = new_tx.transaction_id

            # 4. Tạo bản ghi Debt theo chuẩn ERD (direction = 'PAYABLE')
            debt = Debt(
                transaction_id=transaction_id,
                user_id=user_id,
                customer_id=None,
                supplier_id=supplier_id,
                direction="PAYABLE",          # Mình nợ NCC -> PAYABLE
                original_amount=total_debt_dec,
                remaining_debt=total_debt_dec,
                status="UNPAID",              # Đúng chuẩn enum ERD: 'UNPAID', 'PARTIAL', 'PAID'
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            db.add(debt)
            db.commit()
            db.refresh(debt)

            return {
                "debt_id": debt.debt_id,
                "status": debt.status,
                "total_debt": float(debt.original_amount),
                "original_amount": float(debt.original_amount),
                "remaining_debt": float(debt.remaining_debt),
            }

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi tạo công nợ nhà cung cấp: {str(e)}"
            )

    # =====================================================
    # 5. TRẢ NỢ / THANH TOÁN NỢ NHÀ CUNG CẤP
    # Intent: thu_no_nha_cung_cap / tra_no_nha_cung_cap (pay_supplier_debt)
    #
    # HỖ TRỢ 2 CHẾ ĐỘ:
    #   a) Trả đích danh 1 khoản nợ  -> truyền debt_id
    #   b) Trả theo NCC, tự động     -> truyền supplier_id (KHÔNG truyền debt_id)
    #      phân bổ FIFO qua nhiều     Server tự tìm mọi Debt PAYABLE đang mở của
    #      khoản nợ đang mở           supplier đó, trả từ khoản CŨ NHẤT
    #                                 (created_at tăng dần) trước, hết khoản
    #                                 này mới sang khoản kế tiếp.
    #
    # Lưu ý: Khi trả nợ NCC, tiền bị TRỪ khỏi Account (account.balance - amount)
    # =====================================================
    @staticmethod
    def pay_supplier_debt(
        db: Session,
        user_id: int,
        account_id: int,
        amount: float,
        debt_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Trả tiền nợ cho nhà cung cấp (nợ phải trả - PAYABLE).

        Chế độ 1 - debt_id: trả đích danh cho 1 khoản nợ.
        Chế độ 2 - supplier_id: trả một khoản tiền tổng, tự động phân bổ FIFO
                   (khoản nợ cũ nhất trả trước) qua tất cả Debt đang mở
                   (status IN ('UNPAID','PARTIAL'), direction='PAYABLE')
                   của NCC đó, cho tới khi hết tiền hoặc hết nợ.
        """
        if payment_date is None:
            payment_date = datetime.now()

        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise HTTPException(
                status_code=400,
                detail="Số tiền thanh toán phải lớn hơn 0"
            )

        if not debt_id and not supplier_id:
            raise HTTPException(
                status_code=400,
                detail="Phải truyền debt_id (trả 1 khoản cụ thể) hoặc supplier_id (trả tổng, tự phân bổ FIFO)"
            )

        try:
            # ---------------------------------------------------------
            # Bước 1: xác định danh sách Debt sẽ trả
            # ---------------------------------------------------------
            if debt_id:
                # Chế độ 1: 1 khoản nợ cụ thể
                debt = DebtRepository.get_debt_by_id_and_user(
                    debt_id=debt_id,
                    user_id=user_id,
                    db=db,
                    direction="PAYABLE",
                    for_update=True
                )
                if not debt:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc về bạn"
                    )
                if str(debt.status).upper() == "PAID" or (debt.remaining_debt is not None and Decimal(str(debt.remaining_debt)) <= Decimal("0")):
                    raise HTTPException(
                        status_code=400,
                        detail="Công nợ này đã được thanh toán đầy đủ"
                    )
                debts_to_pay = [debt]
            else:
                # Chế độ 2: FIFO theo supplier_id
                supplier = DebtRepository.get_supplier_by_id_and_user(
                    supplier_id=supplier_id,
                    user_id=user_id,
                    db=db
                )
                if not supplier:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý"
                    )

                debts_to_pay = DebtRepository.get_open_debts_by_supplier_and_user(
                    db=db,
                    supplier_id=supplier_id,
                    user_id=user_id,
                    direction="PAYABLE",
                    order_by="created_at asc",
                    for_update=True
                )
                if not debts_to_pay:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Nhà cung cấp {supplier_id} hiện không có khoản nợ nào đang mở"
                    )

            # ---------------------------------------------------------
            # Bước 2: validate tổng tiền trả so với TỔNG nợ còn lại
            # ---------------------------------------------------------
            remaining_map = {}
            total_remaining = Decimal("0")
            for d in debts_to_pay:
                r = Decimal(str(d.remaining_debt)) if d.remaining_debt is not None else Decimal(str(d.original_amount or 0))
                remaining_map[d.debt_id] = r
                total_remaining += r

            if total_remaining <= Decimal("0"):
                raise HTTPException(
                    status_code=400,
                    detail="Các khoản công nợ này đã được thanh toán đầy đủ"
                )

            if amount_dec > total_remaining:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Số tiền thanh toán ({amount_dec}) vượt quá tổng số nợ hiện có "
                        f"({total_remaining}). Vui lòng nhập số tiền nhỏ hơn hoặc bằng {total_remaining}."
                    )
                )

            # ---------------------------------------------------------
            # Bước 3: kiểm tra tài khoản nguồn trích tiền & số dư
            # ---------------------------------------------------------
            account = DebtRepository.get_account_by_id_and_user(
                account_id=account_id,
                user_id=user_id,
                db=db,
                for_update=True
            )
            if not account:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa"
                )

            current_balance = Decimal(str(account.balance)) if account.balance is not None else Decimal("0")
            if current_balance < amount_dec:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số dư tài khoản ({current_balance}) không đủ để thanh toán ({amount_dec})"
                )

            intent_id = _get_intent_id(db, "tra_no_nha_cung_cap")

            # ---------------------------------------------------------
            # Bước 4: tạo 1 Transaction duy nhất cho cả lượt chi trả
            # ---------------------------------------------------------
            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=None,
                supplier_id=supplier_id if supplier_id else debts_to_pay[0].supplier_id,
                total_amount=amount_dec,
                payment_status="PAID",       # Tiền chi trả ngay -> PAID
                input_method="MANUAL",
                input_text=note or "Trả nợ nhà cung cấp",
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            # ---------------------------------------------------------
            # Bước 5: phân bổ FIFO qua từng Debt
            # ---------------------------------------------------------
            amount_left = amount_dec
            payments_created = []
            debts_summary = []

            for d in debts_to_pay:
                if amount_left <= Decimal("0"):
                    break

                remaining_before = remaining_map[d.debt_id]
                if remaining_before <= Decimal("0"):
                    continue

                allocated = min(amount_left, remaining_before)

                orig_amount = Decimal(str(d.original_amount)) if d.original_amount else allocated
                payment_percentage = (
                    (allocated / orig_amount * 100).quantize(Decimal("0.01"))
                    if orig_amount > 0 else Decimal("0.00")
                )

                debt_payment = DebtPayment(
                    debt_id=d.debt_id,
                    transaction_id=new_tx.transaction_id,
                    account_id=account_id,
                    amount=allocated,
                    payment_percentage=payment_percentage,
                    payment_date=payment_date,
                    note=note,
                    created_at=datetime.now(),
                )
                db.add(debt_payment)
                db.flush()
                payments_created.append(debt_payment)

                remaining_after = remaining_before - allocated
                if remaining_after <= Decimal("0"):
                    d.remaining_debt = Decimal("0.00")
                    d.status = "PAID"
                else:
                    d.remaining_debt = remaining_after
                    d.status = "PARTIAL"
                d.updated_at = datetime.now()

                # Cập nhật Transaction gốc tương ứng nếu có
                if getattr(d, "transaction", None):
                    d.transaction.payment_status = d.status
                    d.transaction.updated_at = datetime.now()

                debts_summary.append({
                    "debt_id": d.debt_id,
                    "payment_id": debt_payment.payment_id,
                    "amount_applied": float(allocated),
                    "remaining_debt": float(max(d.remaining_debt, Decimal("0"))),
                    "debt_status": d.status,
                })

                amount_left -= allocated

            # ---------------------------------------------------------
            # Bước 6: trừ tiền khỏi tài khoản (chi trả)
            # ---------------------------------------------------------
            account.balance = current_balance - amount_dec
            account.updated_at = datetime.now()

            db.commit()
            for p in payments_created:
                db.refresh(p)

            # ---------------------------------------------------------
            # Bước 7: trả kết quả
            # ---------------------------------------------------------
            if debt_id:
                d = debts_to_pay[0]
                return {
                    "payment_id": payments_created[0].payment_id if payments_created else None,
                    "debt_id": d.debt_id,
                    "remaining_debt": float(max(d.remaining_debt, Decimal("0"))),
                    "debt_status": d.status,
                    "amount_paid": float(amount_dec),
                }

            remaining_final = max(total_remaining - amount_dec, Decimal("0"))
            return {
                "supplier_id": supplier_id,
                "payment_id": payments_created[0].payment_id if payments_created else None,
                "amount_paid": float(amount_dec),
                "total_remaining_before": float(total_remaining),
                "total_remaining_after": float(remaining_final),
                "remaining_debt": float(remaining_final),
                "debt_status": "PAID" if remaining_final <= Decimal("0") else "PARTIAL",
                "debts": debts_summary,
            }

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi thanh toán công nợ: {str(e)}"
            )

    # =====================================================
    # 6. LẤY DANH SÁCH CÔNG NỢ NHÀ CUNG CẤP (PAYABLE)
    # =====================================================
    @staticmethod
    def get_supplier_debts(
        user_id: int,
        db: Session,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = DebtRepository.get_supplier_debts(
            user_id=user_id,
            db=db,
            supplier_id=supplier_id,
            status=status,
            search=search
        )

        return [
            DebtService.format_debt(result)
            for result in results
        ]

    # =====================================================
    # 4. LẤY TẤT CẢ CÔNG NỢ THEO USER
    # =====================================================
    @staticmethod
    def get_all_debts(
        user_id: int,
        db: Session,
        name: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = DebtRepository.get_all_by_user(
            user_id=user_id,
            db=db,
            name=name,
            direction=direction,
            status=status,
        )

        return [
            DebtService.format_debt(result)
            for result in results
        ]

    # =====================================================
    # HELPER: FORMAT OUTPUT DEBT RECORD
    # =====================================================
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

        orig_amt = (
            float(debt.original_amount)
            if debt.original_amount is not None
            else 0.0
        )

        rem_debt = (
            float(debt.remaining_debt)
            if debt.remaining_debt is not None
            else 0.0
        )

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

    # =====================================================
    # 8. TẠO CÔNG NỢ GẮN VỚI GIAO DỊCH (BÁN HÀNG / NHẬP HÀNG)
    # =====================================================
    @staticmethod
    def create_receivable_debt_for_transaction(
        db: Session,
        user_id: int,
        customer_id: int,
        transaction_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        """
        Ghi nhận công nợ phải thu (RECEIVABLE) phát sinh từ giao dịch bán hàng.
        """
        return DebtRepository.create_receivable_debt(
            db=db,
            transaction_id=transaction_id,
            user_id=user_id,
            customer_id=customer_id,
            amount=amount,
            status=status,
            flush_only=flush_only,
        )

    @staticmethod
    def create_payable_debt_for_transaction(
        db: Session,
        user_id: int,
        supplier_id: int,
        transaction_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        """
        Ghi nhận công nợ phải trả (PAYABLE) phát sinh từ giao dịch nhập hàng.
        """
        return DebtRepository.create_payable_debt(
            db=db,
            transaction_id=transaction_id,
            user_id=user_id,
            supplier_id=supplier_id,
            amount=amount,
            status=status,
            flush_only=flush_only,
        )

    # =====================================================
    # 9. DASHBOARD SUMMARY (Mục 6.1)
    # =====================================================
    @staticmethod
    def get_summary(user_id: int, db: Session) -> Dict[str, Any]:
        return DebtRepository.get_summary_by_user(user_id=user_id, db=db)

    # =====================================================
    # 10. DANH SÁCH DEBT PHÂN TRANG & FILTER (Mục 6.2)
    # =====================================================
    @staticmethod
    def get_debts_paginated(
        user_id: int,
        db: Session,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        debts, total = DebtRepository.get_debts_paginated(
            user_id=user_id,
            db=db,
            direction=direction,
            status=status,
            search=search,
            customer_id=customer_id,
            supplier_id=supplier_id,
            page=page,
            limit=limit,
        )
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        items = []
        for debt in debts:
            orig = float(debt.original_amount) if debt.original_amount is not None else 0.0
            rem = float(debt.remaining_debt) if debt.remaining_debt is not None else 0.0
            paid = max(0.0, orig - rem)

            cust_info = None
            if debt.customer:
                cust_info = {
                    "customer_id": debt.customer.customer_id,
                    "customer_name": debt.customer.customer_name,
                    "phone_number": debt.customer.phone_number,
                    "email": debt.customer.email,
                    "address": debt.customer.address,
                    "customer_type": debt.customer.customer_type,
                }

            supp_info = None
            if debt.supplier:
                supp_info = {
                    "supplier_id": debt.supplier.supplier_id,
                    "supplier_name": debt.supplier.supplier_name,
                    "phone_number": debt.supplier.phone_number,
                    "email": debt.supplier.email,
                    "address": debt.supplier.address,
                    "product_group": debt.supplier.product_group,
                    "tax_code": debt.supplier.tax_code,
                    "note": debt.supplier.note,
                }

            tx_info = None
            if debt.transaction:
                details = []
                if hasattr(debt.transaction, "transaction_detail") and debt.transaction.transaction_detail:
                    for td in debt.transaction.transaction_detail:
                        pname = td.product.product_name if td.product else None
                        details.append({
                            "detail_id": td.detail_id,
                            "product_id": td.product_id,
                            "product_name": pname,
                            "quantity": float(td.quantity or 0),
                            "unit": td.unit,
                            "unit_price": float(td.unit_price or 0),
                            "subtotal": float(td.subtotal or 0),
                        })
                tx_intent_name = debt.transaction.intent.intent_name if debt.transaction.intent else None
                tx_intent_type = str(debt.transaction.intent.intent_type) if (debt.transaction.intent and debt.transaction.intent.intent_type) else None
                tx_info = {
                    "transaction_id": debt.transaction.transaction_id,
                    "transaction_date": debt.transaction.transaction_date,
                    "intent_name": tx_intent_name,
                    "intent_type": tx_intent_type,
                    "type": tx_intent_type,
                    "input_text": debt.transaction.input_text,
                    "total_amount": float(debt.transaction.total_amount or 0),
                    "payment_status": str(debt.transaction.payment_status) if debt.transaction.payment_status else None,
                    "details": details,
                }

            items.append({
                "debt_id": debt.debt_id,
                "transaction_id": debt.transaction_id,
                "direction": str(debt.direction),
                "customer": cust_info,
                "supplier": supp_info,
                "original_amount": orig,
                "paid_amount": paid,
                "remaining_debt": rem,
                "status": str(debt.status),
                "transaction": tx_info,
                "created_at": debt.created_at,
                "updated_at": debt.updated_at,
                # Tương thích ngược
                "customer_id": debt.customer_id,
                "customer_name": debt.customer.customer_name if debt.customer else None,
                "supplier_id": debt.supplier_id,
                "supplier_name": debt.supplier.supplier_name if debt.supplier else None,
            })

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        }

    # =====================================================
    # 11. CHI TIẾT DEBT (Mục 6.3 & Mục 9)
    # =====================================================
    @staticmethod
    def get_debt_detail(debt_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        debt = DebtRepository.get_debt_by_id_and_user(debt_id=debt_id, user_id=user_id, db=db)
        if not debt:
            raise HTTPException(
                status_code=404,
                detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        orig = float(debt.original_amount) if debt.original_amount is not None else 0.0
        rem = float(debt.remaining_debt) if debt.remaining_debt is not None else 0.0
        paid = max(0.0, orig - rem)

        cust_info = None
        if debt.customer:
            cust_info = {
                "customer_id": debt.customer.customer_id,
                "customer_name": debt.customer.customer_name,
                "phone_number": debt.customer.phone_number,
                "email": debt.customer.email,
                "address": debt.customer.address,
                "customer_type": debt.customer.customer_type,
            }

        supp_info = None
        if debt.supplier:
            supp_info = {
                "supplier_id": debt.supplier.supplier_id,
                "supplier_name": debt.supplier.supplier_name,
                "phone_number": debt.supplier.phone_number,
                "email": debt.supplier.email,
                "address": debt.supplier.address,
                "product_group": debt.supplier.product_group,
                "tax_code": debt.supplier.tax_code,
                "note": debt.supplier.note,
            }

        debt_info = {
            "original_amount": orig,
            "paid_amount": paid,
            "remaining_debt": rem,
            "status": str(debt.status),
        }

        tx_info = None
        if debt.transaction:
            details = []
            if hasattr(debt.transaction, "transaction_detail") and debt.transaction.transaction_detail:
                for td in debt.transaction.transaction_detail:
                    pname = td.product.product_name if td.product else None
                    details.append({
                        "detail_id": td.detail_id,
                        "product_id": td.product_id,
                        "product_name": pname,
                        "quantity": float(td.quantity or 0),
                        "unit": td.unit,
                        "unit_price": float(td.unit_price or 0),
                        "subtotal": float(td.subtotal or 0),
                    })
                tx_intent_name = debt.transaction.intent.intent_name if debt.transaction.intent else None
                tx_intent_type = str(debt.transaction.intent.intent_type) if (debt.transaction.intent and debt.transaction.intent.intent_type) else None
                tx_info = {
                    "transaction_id": debt.transaction.transaction_id,
                    "transaction_date": debt.transaction.transaction_date,
                    "intent_name": tx_intent_name,
                    "intent_type": tx_intent_type,
                    "type": tx_intent_type,
                    "input_text": debt.transaction.input_text,
                    "total_amount": float(debt.transaction.total_amount or 0),
                    "payment_status": str(debt.transaction.payment_status) if debt.transaction.payment_status else None,
                    "details": details,
                }

        payments_list = []
        if debt.payments:
            sorted_payments = sorted(
                debt.payments,
                key=lambda p: (p.payment_date or datetime.min, p.created_at or datetime.min),
                reverse=True
            )
            for p in sorted_payments:
                acc_info = None
                if p.account:
                    acc_info = {
                        "account_id": p.account.account_id,
                        "account_name": p.account.account_name,
                        "account_type": str(p.account.account_type) if p.account.account_type else None,
                    }
                payments_list.append({
                    "payment_id": p.payment_id,
                    "debt_id": p.debt_id,
                    "transaction_id": p.transaction_id,
                    "account_id": p.account_id,
                    "account": acc_info,
                    "amount": float(p.amount) if p.amount is not None else 0.0,
                    "payment_percentage": float(p.payment_percentage) if p.payment_percentage is not None else None,
                    "payment_date": p.payment_date,
                    "note": p.note,
                    "created_at": p.created_at,
                })

        return {
            "debt_id": debt.debt_id,
            "direction": str(debt.direction),
            "customer": cust_info,
            "supplier": supp_info,
            "debt": debt_info,
            "transaction": tx_info,
            "payments": payments_list,
            # Tương thích ngược
            "original_amount": orig,
            "paid_amount": paid,
            "remaining_debt": rem,
            "status": str(debt.status),
            "transaction_id": debt.transaction_id,
            "created_at": debt.created_at,
            "updated_at": debt.updated_at,
        }

    # =====================================================
    # 12. LỊCH SỬ THANH TOÁN (Mục 6.4 & Mục 12)
    # =====================================================
    @staticmethod
    def get_payment_history(debt_id: int, user_id: int, db: Session) -> List[Dict[str, Any]]:
        payments = DebtRepository.get_payments_by_debt_id(debt_id=debt_id, user_id=user_id, db=db)
        if payments is None:
            raise HTTPException(
                status_code=404,
                detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc quyền quản lý"
            )

        res = []
        for p in payments:
            acc_info = None
            if p.account:
                acc_info = {
                    "account_id": p.account.account_id,
                    "account_name": p.account.account_name,
                    "account_type": str(p.account.account_type) if p.account.account_type else None,
                }
            res.append({
                "payment_id": p.payment_id,
                "debt_id": p.debt_id,
                "transaction_id": p.transaction_id,
                "account_id": p.account_id,
                "account": acc_info,
                "amount": float(p.amount) if p.amount is not None else 0.0,
                "payment_percentage": float(p.payment_percentage) if p.payment_percentage is not None else None,
                "payment_date": p.payment_date,
                "note": p.note,
                "created_at": p.created_at,
            })
        return res

    # =====================================================
    # 13. THANH TOÁN CHÍNH XÁC THEO DEBT_ID (Mục 10 & Mục 11)
    # =====================================================
    @staticmethod
    def pay_debt_exact(
        debt_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Thanh toán đúng theo debt_id (Mục 10 & 11).
        Hỗ trợ cả RECEIVABLE (khách trả) và PAYABLE (trả NCC).
        Đảm bảo atomic và cập nhật số dư tài khoản an toàn.
        """
        amount_dec = Decimal(str(amount))
        if amount_dec <= Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail="Số tiền thanh toán phải lớn hơn 0"
            )

        if payment_date is None:
            payment_date = datetime.now()

        try:
            # 1. Validate Debt
            debt = DebtRepository.get_debt_by_id_and_user(
                debt_id=debt_id,
                user_id=user_id,
                db=db,
                for_update=True
            )
            if not debt:
                raise HTTPException(
                    status_code=404,
                    detail=f"Công nợ {debt_id} không tồn tại hoặc không thuộc quyền quản lý"
                )

            remaining_dec = Decimal(str(debt.remaining_debt or 0))
            if str(debt.status).upper() == "PAID" or remaining_dec <= Decimal("0"):
                raise HTTPException(
                    status_code=400,
                    detail="Công nợ này đã được thanh toán đầy đủ"
                )

            if amount_dec > remaining_dec:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số tiền thanh toán ({amount_dec}) vượt quá số nợ còn lại ({remaining_dec})"
                )

            # 2. Validate Account
            account = DebtRepository.get_account_by_id_and_user(
                account_id=account_id,
                user_id=user_id,
                db=db,
                for_update=True
            )
            if not account or not account.is_active:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa"
                )

            current_balance = Decimal(str(account.balance or 0))
            direction = str(debt.direction).upper()

            if direction == "RECEIVABLE":
                account.balance = current_balance + amount_dec
                intent_name = "thu_no_khach_hang"
                default_note = note or "Thu nợ khách hàng"
            elif direction == "PAYABLE":
                if current_balance < amount_dec:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Số dư tài khoản ({current_balance}) không đủ để thanh toán ({amount_dec})"
                    )
                account.balance = current_balance - amount_dec
                intent_name = "tra_no_nha_cung_cap"
                default_note = note or "Trả nợ nhà cung cấp"
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Chiều công nợ không hợp lệ: {direction}"
                )

            intent_id = _get_intent_id(db, intent_name)

            # 3. Tạo Transaction thanh toán
            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=debt.customer_id,
                supplier_id=debt.supplier_id,
                total_amount=amount_dec,
                payment_status="PAID",
                input_method="MANUAL",
                input_text=default_note,
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            # 4. Tạo DebtPayment
            orig_dec = Decimal(str(debt.original_amount or 0))
            pct = (
                (amount_dec / orig_dec * 100).quantize(Decimal("0.01"))
                if orig_dec > 0 else Decimal("0.00")
            )

            debt_payment = DebtPayment(
                debt_id=debt.debt_id,
                transaction_id=new_tx.transaction_id,
                account_id=account_id,
                amount=amount_dec,
                payment_percentage=pct,
                payment_date=payment_date,
                note=note,
                created_at=datetime.now(),
            )
            db.add(debt_payment)
            db.flush()

            # 5. Cập nhật Debt & Account
            new_remaining = remaining_dec - amount_dec
            debt.remaining_debt = max(Decimal("0.00"), new_remaining)
            debt.status = "PAID" if debt.remaining_debt == 0 else "PARTIAL"
            debt.updated_at = datetime.now()

            if getattr(debt, "transaction", None):
                debt.transaction.payment_status = debt.status
                debt.transaction.updated_at = datetime.now()

            account.updated_at = datetime.now()

            db.commit()
            db.refresh(debt_payment)
            db.refresh(debt)
            db.refresh(account)

            orig_val = float(debt.original_amount)
            rem_val = float(debt.remaining_debt)
            paid_val = max(0.0, orig_val - rem_val)

            return {
                "payment_id": debt_payment.payment_id,
                "debt_id": debt.debt_id,
                "transaction_id": new_tx.transaction_id,
                "amount_paid": float(amount_dec),
                "debt": {
                    "original_amount": orig_val,
                    "paid_amount": paid_val,
                    "remaining_debt": rem_val,
                    "status": str(debt.status),
                },
                "account": {
                    "account_id": account.account_id,
                    "account_name": account.account_name,
                    "balance": float(account.balance),
                }
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi thanh toán công nợ: {str(e)}"
            )

    # =====================================================
    # 14. FIFO PAYMENT CHO CUSTOMER (Mục 13)
    # =====================================================
    @staticmethod
    def pay_customer_debts_fifo(
        customer_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        amount_dec = Decimal(str(amount))
        if amount_dec <= Decimal("0"):
            raise HTTPException(status_code=400, detail="Số tiền thanh toán phải lớn hơn 0")

        if payment_date is None:
            payment_date = datetime.now()

        try:
            customer = DebtRepository.get_customer_by_id_and_user(customer_id=customer_id, user_id=user_id, db=db)
            if not customer:
                raise HTTPException(status_code=404, detail=f"Khách hàng {customer_id} không tồn tại hoặc không thuộc quyền quản lý")

            debts = (
                db.query(Debt)
                .filter(
                    Debt.customer_id == customer_id,
                    Debt.user_id == user_id,
                    Debt.direction == "RECEIVABLE",
                    Debt.status != "PAID",
                    Debt.remaining_debt > 0
                )
                .order_by(Debt.created_at.asc(), Debt.debt_id.asc())
                .with_for_update()
                .all()
            )
            if not debts:
                raise HTTPException(status_code=404, detail=f"Khách hàng {customer_id} hiện không có khoản nợ nào đang mở")

            total_remaining = sum(Decimal(str(d.remaining_debt or 0)) for d in debts)
            if total_remaining <= Decimal("0"):
                raise HTTPException(status_code=400, detail="Các khoản công nợ này đã được thanh toán đầy đủ")

            if amount_dec > total_remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số tiền thanh toán ({amount_dec}) vượt quá tổng số nợ hiện có ({total_remaining})"
                )

            account = DebtRepository.get_account_by_id_and_user(account_id=account_id, user_id=user_id, db=db, for_update=True)
            if not account or not account.is_active:
                raise HTTPException(status_code=404, detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa")

            intent_id = _get_intent_id(db, "thu_no_khach_hang")

            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=customer_id,
                supplier_id=None,
                total_amount=amount_dec,
                payment_status="PAID",
                input_method="MANUAL",
                input_text=note or "Khách thanh toán công nợ",
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            amount_left = amount_dec
            allocations = []
            for d in debts:
                if amount_left <= Decimal("0"):
                    break
                rem = Decimal(str(d.remaining_debt or 0))
                if rem <= Decimal("0"):
                    continue

                applied = min(amount_left, rem)
                orig = Decimal(str(d.original_amount or 0))
                pct = ((applied / orig * 100).quantize(Decimal("0.01")) if orig > 0 else Decimal("0.00"))

                dp = DebtPayment(
                    debt_id=d.debt_id,
                    transaction_id=new_tx.transaction_id,
                    account_id=account_id,
                    amount=applied,
                    payment_percentage=pct,
                    payment_date=payment_date,
                    note=note,
                    created_at=datetime.now(),
                )
                db.add(dp)

                rem_after = rem - applied
                d.remaining_debt = max(Decimal("0.00"), rem_after)
                d.status = "PAID" if d.remaining_debt == 0 else "PARTIAL"
                d.updated_at = datetime.now()
                if getattr(d, "transaction", None):
                    d.transaction.payment_status = d.status

                allocations.append({
                    "debt_id": d.debt_id,
                    "transaction_id": d.transaction_id or new_tx.transaction_id,
                    "amount_applied": float(applied),
                    "remaining_debt": float(d.remaining_debt),
                    "status": str(d.status),
                })
                amount_left -= applied

            account.balance = Decimal(str(account.balance or 0)) + amount_dec
            account.updated_at = datetime.now()

            db.commit()

            final_remaining = max(Decimal("0.00"), total_remaining - amount_dec)
            return {
                "customer_id": customer_id,
                "amount_paid": float(amount_dec),
                "before": {
                    "total_remaining": float(total_remaining)
                },
                "after": {
                    "total_remaining": float(final_remaining)
                },
                "allocations": allocations
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý FIFO công nợ khách hàng: {str(e)}")

    # =====================================================
    # 15. FIFO PAYMENT CHO SUPPLIER (Mục 14)
    # =====================================================
    @staticmethod
    def pay_supplier_debts_fifo(
        supplier_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session,
    ) -> Dict[str, Any]:
        amount_dec = Decimal(str(amount))
        if amount_dec <= Decimal("0"):
            raise HTTPException(status_code=400, detail="Số tiền thanh toán phải lớn hơn 0")

        if payment_date is None:
            payment_date = datetime.now()

        try:
            supplier = DebtRepository.get_supplier_by_id_and_user(supplier_id=supplier_id, user_id=user_id, db=db)
            if not supplier:
                raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} không tồn tại hoặc không thuộc quyền quản lý")

            debts = (
                db.query(Debt)
                .filter(
                    Debt.supplier_id == supplier_id,
                    Debt.user_id == user_id,
                    Debt.direction == "PAYABLE",
                    Debt.status != "PAID",
                    Debt.remaining_debt > 0
                )
                .order_by(Debt.created_at.asc(), Debt.debt_id.asc())
                .with_for_update()
                .all()
            )
            if not debts:
                raise HTTPException(status_code=404, detail=f"Nhà cung cấp {supplier_id} hiện không có khoản nợ nào đang mở")

            total_remaining = sum(Decimal(str(d.remaining_debt or 0)) for d in debts)
            if total_remaining <= Decimal("0"):
                raise HTTPException(status_code=400, detail="Các khoản công nợ này đã được thanh toán đầy đủ")

            if amount_dec > total_remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số tiền thanh toán ({amount_dec}) vượt quá tổng số nợ hiện có ({total_remaining})"
                )

            account = DebtRepository.get_account_by_id_and_user(account_id=account_id, user_id=user_id, db=db, for_update=True)
            if not account or not account.is_active:
                raise HTTPException(status_code=404, detail=f"Tài khoản {account_id} không tồn tại hoặc đã bị vô hiệu hóa")

            current_balance = Decimal(str(account.balance or 0))
            if current_balance < amount_dec:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số dư tài khoản ({current_balance}) không đủ để thanh toán ({amount_dec})"
                )

            intent_id = _get_intent_id(db, "tra_no_nha_cung_cap")

            new_tx = Transaction(
                user_id=user_id,
                intent_id=intent_id,
                account_id=account_id,
                customer_id=None,
                supplier_id=supplier_id,
                total_amount=amount_dec,
                payment_status="PAID",
                input_method="MANUAL",
                input_text=note or "Thanh toán công nợ NCC",
                transaction_date=payment_date,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_tx)
            db.flush()

            amount_left = amount_dec
            allocations = []
            for d in debts:
                if amount_left <= Decimal("0"):
                    break
                rem = Decimal(str(d.remaining_debt or 0))
                if rem <= Decimal("0"):
                    continue

                applied = min(amount_left, rem)
                orig = Decimal(str(d.original_amount or 0))
                pct = ((applied / orig * 100).quantize(Decimal("0.01")) if orig > 0 else Decimal("0.00"))

                dp = DebtPayment(
                    debt_id=d.debt_id,
                    transaction_id=new_tx.transaction_id,
                    account_id=account_id,
                    amount=applied,
                    payment_percentage=pct,
                    payment_date=payment_date,
                    note=note,
                    created_at=datetime.now(),
                )
                db.add(dp)

                rem_after = rem - applied
                d.remaining_debt = max(Decimal("0.00"), rem_after)
                d.status = "PAID" if d.remaining_debt == 0 else "PARTIAL"
                d.updated_at = datetime.now()
                if getattr(d, "transaction", None):
                    d.transaction.payment_status = d.status

                allocations.append({
                    "debt_id": d.debt_id,
                    "transaction_id": d.transaction_id or new_tx.transaction_id,
                    "amount_applied": float(applied),
                    "remaining_debt": float(d.remaining_debt),
                    "status": str(d.status),
                })
                amount_left -= applied

            account.balance = current_balance - amount_dec
            account.updated_at = datetime.now()

            db.commit()

            final_remaining = max(Decimal("0.00"), total_remaining - amount_dec)
            return {
                "supplier_id": supplier_id,
                "amount_paid": float(amount_dec),
                "before": {
                    "total_remaining": float(total_remaining)
                },
                "after": {
                    "total_remaining": float(final_remaining)
                },
                "allocations": allocations
            }
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý FIFO công nợ NCC: {str(e)}")