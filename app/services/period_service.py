import calendar
from datetime import datetime, date, time, timedelta
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
    def get_tz(cls, tz_str: Optional[str] = None):
        tz_name = tz_str or cls.DEFAULT_TIMEZONE
        try:
            return ZoneInfo(tz_name)
        except Exception:
            from datetime import timezone, timedelta
            return timezone(timedelta(hours=7))

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

        # 1. Nếu có cả from_date và to_date (hoặc period_type == "CUSTOM"): ưu tiên theo khoảng ngày
        if (from_date and to_date) or p_type == "CUSTOM":
            res = cls._resolve_custom_range(from_date, to_date, tz)
            if p_type:
                res["period_type"] = p_type
            return res

        # 2. Nếu không có period_type nhưng có from_date hoặc to_date lẻ
        if not p_type and (from_date or to_date):
            return cls._resolve_custom_range(from_date, to_date, tz)

        # Mặc định nếu không truyền gì cả -> DAY của hôm nay
        if not p_type:
            p_type = "DAY"
            date_val = now.date()

        if p_type == "DAY":
            return cls._resolve_day(date_val, tz, now)
        elif p_type == "WEEK":
            d = cls._parse_date(date_val) if date_val else now.date()
            monday = d - timedelta(days=d.weekday())
            sunday = monday + timedelta(days=6)
            res = cls._resolve_custom_range(monday, sunday, tz)
            res["period_type"] = "WEEK"
            return res
        elif p_type == "MONTH":
            return cls._resolve_month(year, month, tz, now)
        elif p_type == "QUARTER":
            return cls._resolve_quarter(year, quarter, tz, now)
        elif p_type == "YEAR":
            return cls._resolve_year(year, tz, now)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại kỳ '{period_type}' không hợp lệ. Chỉ chấp nhận: DAY, WEEK, MONTH, QUARTER, YEAR, CUSTOM."
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
            # Yêu cầu định dạng chính xác YYYY-MM-DD không có ký tự thừa / SQL injection
            try:
                if len(val) != 10:
                    raise ValueError()
                return datetime.strptime(val, "%Y-%m-%d").date()
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
    def _validate_year(cls, year: Optional[int], now: datetime) -> int:
        if year is not None:
            if not isinstance(year, int) or year < 1900 or year > 2100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Năm '{year}' không hợp lệ. Năm phải nằm trong khoảng 1900 đến 2100."
                )
            return year
        return now.year

    @classmethod
    def _resolve_month(cls, year: Optional[int], month: Optional[int], tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        y = cls._validate_year(year, now)
        if month is None:
            m = now.month
        else:
            if not isinstance(month, int) or not (1 <= month <= 12):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tháng '{month}' không hợp lệ. Tháng phải nằm trong khoảng 1 đến 12."
                )
            m = month

        last_day = calendar.monthrange(y, m)[1]
        start_d = date(y, m, 1)
        end_d = date(y, m, last_day)
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)

        return {
            "period_type": "MONTH",
            "period_start": start_d,
            "period_end": end_d,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "year": y,
            "month": m,
            "quarter": (m - 1) // 3 + 1
        }

    @classmethod
    def _resolve_quarter(cls, year: Optional[int], quarter: Optional[int], tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        y = cls._validate_year(year, now)
        if quarter is None:
            q = (now.month - 1) // 3 + 1
        else:
            if not isinstance(quarter, int) or not (1 <= quarter <= 4):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Quý '{quarter}' không hợp lệ. Quý phải từ 1 đến 4."
                )
            q = quarter

        quarter_map = {
            1: (date(y, 1, 1), date(y, 3, 31)),
            2: (date(y, 4, 1), date(y, 6, 30)),
            3: (date(y, 7, 1), date(y, 9, 30)),
            4: (date(y, 10, 1), date(y, 12, 31))
        }

        start_d, end_d = quarter_map[q]
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max)

        return {
            "period_type": "QUARTER",
            "period_start": start_d,
            "period_end": end_d,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "year": y,
            "quarter": q
        }

    @classmethod
    def _resolve_year(cls, year: Optional[int], tz: ZoneInfo, now: datetime) -> Dict[str, Any]:
        y = cls._validate_year(year, now)
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
