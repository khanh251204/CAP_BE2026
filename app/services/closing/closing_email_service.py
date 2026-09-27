import logging
from decimal import Decimal
from typing import Dict, Any
from datetime import datetime, date

from app.models.closing_period_model import ClosingPeriod
from app.models.user_model import User
from app.services.email_service import send_email

logger = logging.getLogger(__name__)


class ClosingEmailService:
    @classmethod
    def _dispatch_closing_email(
        cls,
        user: User,
        closing: ClosingPeriod,
        summary: Dict[str, Any],
        transaction_count: int
    ):
        """
        Hàm helper gửi email báo cáo tổng kết kỳ chốt sổ tới email người dùng.
        """
        recipient_email = getattr(user, "email", None)
        if not recipient_email:
            raise ValueError("Người dùng không có email hợp lệ để nhận báo cáo.")

        user_name = getattr(user, "full_name", None) or "Quý khách"
        store_name = getattr(user, "store_name", None) or "Cửa hàng"

        def safe_int(v):
            try:
                return int(Decimal(str(v or 0)))
            except Exception:
                return 0

        total_sales_val = safe_int(summary.get("total_sales"))
        total_purchase_val = safe_int(summary.get("total_purchase"))
        total_income_val = safe_int(summary.get("total_income"))
        total_expense_val = safe_int(summary.get("total_expense"))
        cogs_val = safe_int(summary.get("cogs"))
        op_expense_val = safe_int(summary.get("operating_expense"))
        profit_val = safe_int(summary.get("profit"))
        total_receivable_val = safe_int(summary.get("total_receivable"))
        total_payable_val = safe_int(summary.get("total_payable"))

        period_label = f"Kỳ {closing.period_type} ({closing.period_start} đến {closing.period_end})"
        subject = f"[{store_name}] Báo cáo chốt sổ {period_label}"

        closed_dt = closing.closed_at if isinstance(closing.closed_at, (datetime, date)) else datetime.now()
        closed_str = closed_dt.strftime("%d/%m/%Y %H:%M:%S")

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="text-align: center; border-bottom: 2px solid #2563eb; padding-bottom: 15px;">
                <h2 style="color: #2563eb; margin: 0;">BÁO CÁO CHỐT SỔ TÀI CHÍNH</h2>
                <p style="margin: 5px 0 0; color: #666;">{store_name} — {period_label}</p>
            </div>
            
            <p style="margin-top: 20px;">Xin chào <strong>{user_name}</strong>,</p>
            <p>Hệ thống xin gửi tới bạn bảng tổng kết tài chính của kỳ chốt sổ vừa hoàn tất:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Doanh thu bán hàng:</strong></td>
                    <td style="padding: 10px; text-align: right; color: #16a34a; font-weight: bold;">{total_sales_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Giá vốn hàng bán (COGS):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #64748b; font-weight: bold;">{cogs_val:,} đ</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Chi phí hoạt động:</strong></td>
                    <td style="padding: 10px; text-align: right; color: #dc2626; font-weight: bold;">{op_expense_val:,} đ</td>
                </tr>
                <tr style="background-color: #eff6ff; border-bottom: 2px solid #3b82f6;">
                    <td style="padding: 10px;"><strong>Lợi nhuận ước tính:</strong></td>
                    <td style="padding: 10px; text-align: right; color: {'#16a34a' if profit_val >= 0 else '#dc2626'}; font-weight: bold; font-size: 16px;">{profit_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Tổng nhập hàng (Mua hàng):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #ea580c; font-weight: bold;">{total_purchase_val:,} đ</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Tổng tiền thực thu:</strong></td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{total_income_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Tổng tiền thực chi:</strong></td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{total_expense_val:,} đ</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Công nợ phải thu (Khách nợ):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #2563eb; font-weight: bold;">{total_receivable_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Công nợ phải trả (Nợ NCC):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #dc2626; font-weight: bold;">{total_payable_val:,} đ</td>
                </tr>
                <tr style="background-color: #f1f5f9;">
                    <td style="padding: 10px;"><strong>Tổng số giao dịch:</strong></td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{transaction_count}</td>
                </tr>
            </table>

            <p style="font-size: 13px; color: #64748b;">Thời điểm chốt: {closed_str}</p>
            <p style="font-size: 13px; color: #64748b;">Mã kỳ chốt: #{closing.closing_id}</p>
            
            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center;">
                Email được gửi tự động từ hệ thống quản lý tài chính VoiceCashBook.
            </div>
        </body>
        </html>
        """

        send_email(
            to_email=recipient_email,
            subject=subject,
            text_content=f"Báo cáo chốt sổ {period_label}: Doanh thu: {summary.get('total_sales', 0)} đ, Tổng thu: {summary.get('total_income', 0)} đ, Tổng chi: {summary.get('total_expense', 0)} đ.",
            html_content=html_body
        )
