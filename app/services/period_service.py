import calendar
from datetime import datetime, date, time
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo
# pyrefly: ignore [missing-import]
from fastapi import HTTPException, status


class PeriodService:
    """
    Common Period Service to resolve and validate periods:
    DAY, MONTH, QUARTER, YEAR (and custom date range).
    Used across ReportService, ClosingService, and Schedulers.
    """

    DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"

    @classmethod
    def get_tz(cls, tz_str: Optional[str] = None) -> ZoneInfo:
        tz_name = tz_str or cls.DEFAULT_TIMEZONE
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return ZoneInfo(cls.DEFAULT_TIMEZONE)

    @classmethod
    def get_now(cls, tz_str: Optional[str] = None) -> datetime:
        return datetime.now(cls.get_tz(tz_str))

    @classmethod
    def resolve_period(
        cls,
        period_type: Optional[str] = None,
        date_val: Optional[str | date] = None,
        date: Optional[str | date] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        quarter: Optional[int] = None,
        from_date: Optional[str | date] = None,
        to_date: Optional[str | date] = None,
        tz_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Xác định chính xác period_start, period_end và khoảng datetime (start_datetime, end_datetime).
        
        Quy tắc:
        - DAY: bắt buộc date_val hoặc date (nếu thiếu có thể fallback về ngày hôm nay theo timezone).
        - MONTH: bắt buộc year và month (1 <= month <= 12).
        - QUARTER: bắt buộc year và quarter (1 <= quarter <= 4).
        - YEAR: bắt buộc year.
        - CUSTOM (hoặc fallback khi có from_date và to_date): giải quyết theo khoảng ngày.
        """
        date_val = date_val or date
        tz = cls.get_tz(tz_str)
        now = datetime.now(tz)

        # Chuẩn hóa period_type nếu có
        p_type = period_type.upper() if period_type else None

        # Nếu không có period_type nhưng có from_date / to_date
        if not p_type and (from_date or to_date):
            return cls._resolve_custom_range(from_date, to_date, tz)

        # Mặc định nếu không truyền gì cả -> DAY của hôm nay
        if not p_type:
            p_type = "DAY"
            date_val = now.date()

        if p_type == "DAY":
            return cls._resolve_day(date_val, tz, now)
        elif p_type == "MONTH":
            return cls._resolve_month(year, month, tz, now)
        elif p_type == "QUARTER":
            return cls._resolve_quarter(year, quarter, tz, now)
        elif p_type == "YEAR":
            return cls._resolve_year(year, tz, now)
        elif p_type == "CUSTOM":
            return cls._resolve_custom_range(from_date, to_date, tz)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại kỳ '{period_type}' không hợp lệ. Chỉ chấp nhận: DAY, MONTH, QUARTER, YEAR."
            )

    @classmethod
    def _parse_date(cls, val: Any) -> Optional[date]:
        if not val:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            val = val.strip()
            # Thử parse ISO format YYYY-MM-DD
            try:
                return datetime.strptime(val[:10], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Định dạng ngày '{val}' không hợp lệ. Yêu cầu format YYYY-MM-DD."
                )
        return None

    @classmethod
    def _resolve_day(cls, date_val: Any, tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        d = cls._parse_date(date_val) if date_val else now.date()
        start_dt = datetime.combine(d, time.min)
        end_dt = datetime.combine(d, time.max)
        return {
            "period_type": "DAY",
            "period_start": d,
            "period_end": d,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "date": d.isoformat(),
            "year": d.year,
            "month": d.month,
            "quarter": (d.month - 1) // 3 + 1
        }

    @classmethod
    def _resolve_month(cls, year: Optional[int], month: Optional[int], tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        y = year or now.year
        if month is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="period_type = MONTH bắt buộc phải truyền 'month'."
            )
        if not (1 <= month <= 12):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tháng '{month}' không hợp lệ. Tháng phải nằm trong khoảng 1 đến 12."
            )

        last_day = calendar.monthrange(y, month)[1]
        start_d = date(y, month, 1)
        end_d = date(y, month, last_day)
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)

        return {
            "period_type": "MONTH",
            "period_start": start_d,
            "period_end": end_d,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "year": y,
            "month": month,
            "quarter": (month - 1) // 3 + 1
        }

    @classmethod
    def _resolve_quarter(cls, year: Optional[int], quarter: Optional[int], tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        y = year or now.year
        if quarter is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="period_type = QUARTER bắt buộc phải truyền 'quarter'."
            )
        if not (1 <= quarter <= 4):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quý '{quarter}' không hợp lệ. Quý phải từ 1 đến 4."
            )

        quarter_map = {
            1: (date(y, 1, 1), date(y, 3, 31)),
            2: (date(y, 4, 1), date(y, 6, 30)),
            3: (date(y, 7, 1), date(y, 9, 30)),
            4: (date(y, 10, 1), date(y, 12, 31))
        }

        start_d, end_d = quarter_map[quarter]
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)

        return {
            "period_type": "QUARTER",
            "period_start": start_d,
            "period_end": end_d,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "year": y,
            "quarter": quarter
        }

    @classmethod
    def _resolve_year(cls, year: Optional[int], tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        y = year or now.year
        start_d = date(y, 1, 1)
        end_d = date(y, 12, 31)
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)

        return {
            "period_type": "YEAR",
            "period_start": start_d,
            "period_end": end_d,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "year": y
        }

    @classmethod
    def _resolve_custom_range(cls, from_date: Any, to_date: Any, tz: ZoneInfo) -> Dict[str, Any]:
        start_d = cls._parse_date(from_date) if from_date else date.today()
        end_d = cls._parse_date(to_date) if to_date else start_d

        if start_d > end_d:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ngày bắt đầu '{start_d}' không được lớn hơn ngày kết thúc '{end_d}'."
            )

        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)

        return {
            "period_type": "CUSTOM",
            "period_start": start_d,
            "period_end": end_d,
            "start_datetime": start_dt,
            "end_datetime": end_dt
        }
