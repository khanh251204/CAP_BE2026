from typing import Dict, Any
from datetime import datetime, time
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.closing_setting_model import ClosingSetting


class ClosingSettingService:
    @classmethod
    def get_closing_settings(cls, db: Session, user_id: int) -> Dict[str, Any]:
        """
        GET /closing-settings: Lấy cấu hình tự động chốt sổ.
        """
        setting = db.query(ClosingSetting).filter(ClosingSetting.user_id == user_id).first()
        if not setting:
            setting = ClosingSetting(
                user_id=user_id,
                period_type="DAY",
                closing_time=time(23, 0, 0),
                auto_close=False,
                send_report=True,
                report_channel="EMAIL",
                timezone="Asia/Ho_Chi_Minh",
                is_active=True
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)

        return {
            "setting_id": setting.setting_id,
            "user_id": setting.user_id,
            "period_type": setting.period_type,
            "closing_time": setting.closing_time.strftime("%H:%M:%S"),
            "auto_close": setting.auto_close,
            "send_report": setting.send_report,
            "report_channel": setting.report_channel,
            "timezone": setting.timezone,
            "is_active": setting.is_active
        }

    @classmethod
    def update_closing_settings(
        cls,
        db: Session,
        user_id: int,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        PUT /closing-settings: Cập nhật cấu hình tự động chốt sổ.
        """
        setting = db.query(ClosingSetting).filter(ClosingSetting.user_id == user_id).first()
        if not setting:
            setting = ClosingSetting(user_id=user_id)
            db.add(setting)

        if "period_type" in update_data and update_data["period_type"] is not None:
            pt = update_data["period_type"].upper()
            if pt not in ["DAY", "MONTH", "QUARTER", "YEAR"]:
                raise HTTPException(status_code=400, detail="period_type không hợp lệ.")
            setting.period_type = pt

        if "closing_time" in update_data and update_data["closing_time"] is not None:
            t_str = update_data["closing_time"].strip()
            try:
                if len(t_str.split(":")) == 2:
                    t_str += ":00"
                setting.closing_time = datetime.strptime(t_str, "%H:%M:%S").time()
            except ValueError:
                raise HTTPException(status_code=400, detail="closing_time phải có format HH:MM hoặc HH:MM:SS.")

        for field in ["auto_close", "send_report", "report_channel", "timezone", "is_active"]:
            if field in update_data and update_data[field] is not None:
                setattr(setting, field, update_data[field])

        setting.updated_at = datetime.now()
        db.commit()
        db.refresh(setting)
        return cls.get_closing_settings(db, user_id)
