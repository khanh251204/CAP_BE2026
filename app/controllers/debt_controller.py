from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.services.debt_service import DebtService
from app.services.websocket_manager import trigger_report_update


class DebtController:

    # ==========================================
    # TẠO CÔNG NỢ KHÁCH HÀNG (GHI NỢ)
    # ==========================================
    @staticmethod
    def create_customer_debt(
        db: Session,
        user_id: int,
        customer_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        res = DebtService.create_customer_debt(
            db=db,
            user_id=user_id,
            customer_id=customer_id,
            total_debt=total_debt,
            transaction_id=transaction_id,
            note=note,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable"])
        except Exception:
            pass
        return res

    # ==========================================
    # THU TIỀN NỢ KHÁCH HÀNG (THU NỢ)
    # ==========================================
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
        res = DebtService.collect_customer_debt(
            db=db,
            user_id=user_id,
            debt_id=debt_id,
            customer_id=customer_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable", "balance"])
        except Exception:
            pass
        return res

    # ==========================================
    # LẤY DANH SÁCH NỢ KHÁCH HÀNG
    # ==========================================
    @staticmethod
    def get_customer_debts(
        user_id: int,
        db: Session,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return DebtService.get_customer_debts(
            user_id=user_id,
            db=db,
            customer_id=customer_id,
            status=status,
            search=search
        )

    # ==========================================
    # TẠO CÔNG NỢ NHÀ CUNG CẤP (GHI NỢ)
    # ==========================================
    @staticmethod
    def create_supplier_debt(
        db: Session,
        user_id: int,
        supplier_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        res = DebtService.create_supplier_debt(
            db=db,
            user_id=user_id,
            supplier_id=supplier_id,
            total_debt=total_debt,
            transaction_id=transaction_id,
            note=note,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "payable"])
        except Exception:
            pass
        return res

    # ==========================================
    # TRẢ TIỀN NỢ NHÀ CUNG CẤP (TRẢ NỢ)
    # ==========================================
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
        res = DebtService.pay_supplier_debt(
            db=db,
            user_id=user_id,
            debt_id=debt_id,
            supplier_id=supplier_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "payable", "balance"])
        except Exception:
            pass
        return res

    # ==========================================
    # LẤY DANH SÁCH NỢ NHÀ CUNG CẤP
    # ==========================================
    @staticmethod
    def get_supplier_debts(
        user_id: int,
        db: Session,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return DebtService.get_supplier_debts(
            user_id=user_id,
            db=db,
            supplier_id=supplier_id,
            status=status,
            search=search
        )

    # ==========================================
    # LẤY TẤT CẢ CÔNG NỢ
    # ==========================================
    @staticmethod
    def get_all_debts(
        user_id: int,
        db: Session,
        name: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return DebtService.get_all_debts(
            user_id=user_id,
            db=db,
            name=name,
            direction=direction,
            status=status,
        )

    # ==========================================
    # DASHBOARD SUMMARY (Mục 6.1)
    # ==========================================
    @staticmethod
    def get_summary(
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        return DebtService.get_summary(user_id=user_id, db=db)

    # ==========================================
    # DANH SÁCH PHÂN TRANG (Mục 6.2)
    # ==========================================
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
        limit: int = 20
    ) -> Dict[str, Any]:
        return DebtService.get_debts_paginated(
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

    # ==========================================
    # CHI TIẾT CÔNG NỢ (Mục 6.3)
    # ==========================================
    @staticmethod
    def get_debt_detail(
        debt_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        return DebtService.get_debt_detail(debt_id=debt_id, user_id=user_id, db=db)

    # ==========================================
    # LỊCH SỬ THANH TOÁN (Mục 6.4)
    # ==========================================
    @staticmethod
    def get_payment_history(
        debt_id: int,
        user_id: int,
        db: Session
    ) -> List[Dict[str, Any]]:
        return DebtService.get_payment_history(debt_id=debt_id, user_id=user_id, db=db)

    # ==========================================
    # THANH TOÁN CHÍNH XÁC THEO DEBT_ID (Mục 10 & 11)
    # ==========================================
    @staticmethod
    def pay_debt_exact(
        debt_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        res = DebtService.pay_debt_exact(
            debt_id=debt_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
            user_id=user_id,
            db=db
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable", "payable", "balance"])
        except Exception:
            pass
        return res

    # ==========================================
    # FIFO CUSTOMER PAYMENT (Mục 13)
    # ==========================================
    @staticmethod
    def pay_customer_debts_fifo(
        customer_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        res = DebtService.pay_customer_debts_fifo(
            customer_id=customer_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
            user_id=user_id,
            db=db
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable", "balance"])
        except Exception:
            pass
        return res

    # ==========================================
    # FIFO SUPPLIER PAYMENT (Mục 14)
    # ==========================================
    @staticmethod
    def pay_supplier_debts_fifo(
        supplier_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime],
        note: Optional[str],
        user_id: int,
        db: Session
    ) -> Dict[str, Any]:
        res = DebtService.pay_supplier_debts_fifo(
            supplier_id=supplier_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
            user_id=user_id,
            db=db
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "payable", "balance"])
        except Exception:
            pass
        return res
