from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.services.debt_service import DebtService


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
        return DebtService.create_customer_debt(
            db=db,
            user_id=user_id,
            customer_id=customer_id,
            total_debt=total_debt,
            transaction_id=transaction_id,
            note=note,
        )

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
        return DebtService.collect_customer_debt(
            db=db,
            user_id=user_id,
            debt_id=debt_id,
            customer_id=customer_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
        )

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
        return DebtService.create_supplier_debt(
            db=db,
            user_id=user_id,
            supplier_id=supplier_id,
            total_debt=total_debt,
            transaction_id=transaction_id,
            note=note,
        )

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
        return DebtService.pay_supplier_debt(
            db=db,
            user_id=user_id,
            debt_id=debt_id,
            supplier_id=supplier_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
        )

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
