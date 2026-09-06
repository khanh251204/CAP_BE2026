"""
Debt Service — Quản lý công nợ khách hàng & nhà cung cấp theo ERD.

Cung cấp các chức năng chính:
  - create_customer_debt  (POST /debts/customer)              -> Ghi nợ khách hàng (intent: ghi_no_khach_hang)
  - collect_customer_debt (POST /debts/customer/{debt_id}/payments hoặc /debts/customer/payments) -> Thu tiền nợ khách hàng (intent: thu_no_khach_hang)
  - get_customer_debts    (GET /debts/customer)               -> Danh sách công nợ khách hàng
  - get_all_debts         (GET /debts/)                       -> Danh sách toàn bộ công nợ
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.account_model import Account
from app.models.customer_model import Customer
from app.models.intent_model import Intent
from app.repositories.debt_repository import DebtRepository


# =========================================================
# Helper: lấy intent_id an toàn từ database
# =========================================================
def _get_intent_id(db: Session, intent_name: str, fallback_type: str = "DEBT") -> Optional[int]:
    """
    Tra cứu intent_id theo tên intent. Nếu không tìm thấy, fallback tìm theo loại intent
    hoặc intent đầu tiên trong DB để đảm bảo không crash trong môi trường test/chưa seed.
    """
    intent = (
        db.query(Intent)
        .filter(Intent.intent_name.ilike(intent_name))
        .first()
    )

    if intent:
        return intent.intent_id

    # Fallback theo intent_type
    intent = (
        db.query(Intent)
        .filter(Intent.intent_type == fallback_type)
        .first()
    )
    if intent:
        return intent.intent_id

    # Fallback lấy bất kỳ intent nào nếu có
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
                    direction="RECEIVABLE"
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
                db=db
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

        if isinstance(result, (list, tuple)) or hasattr(result, "_mapping"):
            debt = result[0]
            customer_name = result[1] if len(result) > 1 else None
            supplier_name = result[2] if len(result) > 2 else None
        else:
            debt = result

            customer = getattr(debt, "customer", None)
            supplier = getattr(debt, "supplier", None)

            customer_name = (
                getattr(customer, "customer_name", None)
                if customer else None
            )

            supplier_name = (
                getattr(supplier, "supplier_name", None)
                if supplier else None
            )

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