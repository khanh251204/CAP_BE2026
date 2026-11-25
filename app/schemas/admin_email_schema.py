from typing import List, Optional
from pydantic import BaseModel, Field


class AdminEmailSettingsUpdateRequest(BaseModel):
    send_on_ai_subscribe: Optional[bool] = None
    auto_expiry_reminder: Optional[bool] = None
    expiry_reminder_days: Optional[int] = Field(default=None, ge=1, le=30)
    renewal_reminder_enabled: Optional[bool] = None
    renewal_reminder_after_days: Optional[int] = Field(default=None, ge=0, le=60)
    schedule_hour: Optional[int] = Field(default=None, ge=0, le=23)
    schedule_interval_hours: Optional[int] = Field(default=None, ge=1, le=24)
    confirm_subject_template: Optional[str] = Field(default=None, max_length=200)
    confirm_body_note: Optional[str] = Field(default=None, max_length=1000)
    reminder_subject_template: Optional[str] = Field(default=None, max_length=200)
    reminder_body_note: Optional[str] = Field(default=None, max_length=1000)
    renewal_subject_template: Optional[str] = Field(default=None, max_length=200)
    renewal_body_note: Optional[str] = Field(default=None, max_length=1000)


class AdminSendTestEmailRequest(BaseModel):
    to_email: str = Field(..., min_length=5, max_length=255)


class AdminSendCustomEmailRequest(BaseModel):
    mode: str = Field(default="SINGLE", description="SINGLE | EXPIRING_AI | ALL_ACTIVE_USERS")
    to_emails: List[str] = Field(default_factory=list)
    subject: str = Field(..., min_length=1, max_length=255)
    body_text: str = Field(..., min_length=1, max_length=10000)
