import math
from datetime import datetime, date, time
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models.system_log_model import SystemLog, SystemLogLevel, SystemLogStep


class AdminSystemLogService:

    @staticmethod
    def list_logs(
        db: Session,
        level: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        keyword: Optional[str] = None,
        step: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[SystemLog], int, int]:
        """
        Lấy danh sách System Logs có phân trang và bộ lọc linh hoạt.
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        query = db.query(SystemLog)

        if level:
            query = query.filter(SystemLog.level == level.upper().strip())

        if step:
            query = query.filter(SystemLog.step == step.upper().strip())

        if date_from:
            query = query.filter(SystemLog.created_at >= date_from)

        if date_to:
            # Nếu date_to không có giờ cụ thể, mở rộng đến hết ngày
            if date_to.time() == time(0, 0, 0):
                date_to = datetime.combine(date_to.date(), time(23, 59, 59, 999999))
            query = query.filter(SystemLog.created_at <= date_to)

        if keyword:
            kw = f"%{keyword.strip()}%"
            filters = [
                SystemLog.message.ilike(kw),
                SystemLog.api_path.ilike(kw),
                SystemLog.request_id.ilike(kw),
            ]
            if keyword.strip().isdigit():
                filters.append(SystemLog.user_id == int(keyword.strip()))
            query = query.filter(or_(*filters))

        total_items = query.count()
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0

        items = (
            query.order_by(SystemLog.created_at.desc(), SystemLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return items, total_items, total_pages

    @staticmethod
    def get_summary(
        db: Session,
        target_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tính toán các chỉ số sức khỏe hệ thống trong một ngày:
        - total_requests
        - success_rate (%)
        - error_count
        - warning_count
        - avg_processing_ms (cho voice endpoints)
        - p95_processing_ms (cho voice endpoints)
        """
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                target_date = date.today()
        else:
            target_date = date.today()

        start_dt = datetime.combine(target_date, time(0, 0, 0))
        end_dt = datetime.combine(target_date, time(23, 59, 59, 999999))

        base_query = db.query(SystemLog).filter(
            SystemLog.created_at >= start_dt,
            SystemLog.created_at <= end_dt
        )

        # Tổng số request (tính các log ghi nhận HTTP request hoặc tổng log)
        total_requests = base_query.count()

        # Số lỗi và cảnh báo
        error_count = base_query.filter(SystemLog.level == SystemLogLevel.ERROR.value).count()
        warning_count = base_query.filter(SystemLog.level == SystemLogLevel.WARNING.value).count()

        # Tính tỷ lệ thành công:
        # Nếu có HTTP request (status_code không None), tính theo status_code < 400
        http_requests = base_query.filter(SystemLog.status_code.isnot(None))
        http_count = http_requests.count()

        if http_count > 0:
            success_count = http_requests.filter(
                SystemLog.status_code >= 200,
                SystemLog.status_code < 400
            ).count()
            success_rate = round((success_count / http_count) * 100.0, 2)
        elif total_requests > 0:
            success_rate = round(((total_requests - error_count) / total_requests) * 100.0, 2)
        else:
            success_rate = 100.0

        # Thống kê latency cho voice endpoints:
        # Voice endpoints gồm api_path chứa stt / analyze hoặc step là STT / LLM
        voice_query = base_query.filter(
            SystemLog.duration_ms.isnot(None),
            or_(
                SystemLog.api_path.ilike("%/stt%"),
                SystemLog.api_path.ilike("%/analyze%"),
                SystemLog.step.in_([SystemLogStep.STT.value, SystemLogStep.LLM.value])
            )
        )

        durations = [row[0] for row in voice_query.with_entities(SystemLog.duration_ms).all() if row[0] is not None]

        if durations:
            avg_processing_ms = round(sum(durations) / len(durations), 2)
            durations.sort()
            p95_index = max(0, math.ceil(0.95 * len(durations)) - 1)
            p95_processing_ms = float(durations[p95_index])
        else:
            avg_processing_ms = 0.0
            p95_processing_ms = 0.0

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "total_requests": total_requests,
            "success_rate": success_rate,
            "error_count": error_count,
            "warning_count": warning_count,
            "avg_processing_ms": avg_processing_ms,
            "p95_processing_ms": p95_processing_ms,
        }
