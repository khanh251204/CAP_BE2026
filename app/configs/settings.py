"""
Centralized Application Settings using Pydantic BaseSettings.
Loads from environment variables and .env file.
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 1. Environment & Server
    APP_ENV: str = Field("development", description="Environment: development, staging, production")
    ENVIRONMENT: Optional[str] = Field(None, description="Environment alias for deployment (e.g. production)")
    CORS_ORIGINS: str = Field(
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        description="Comma-separated list of allowed CORS origins"
    )
    REDIS_URL: Optional[str] = Field(None, description="Optional Redis connection URL for distributed caching/sessions")

    # 2. Database Connection
    MYSQL_TRACKER_URL: str = Field(
        ...,
        description="MySQL / TiDB database connection URL"
    )

    # 3. AI Service Keys
    GROQ_API_KEY: Optional[str] = Field(None, description="Groq API Key for Whisper STT and LLM")
    GROQ_API_KEY_2: Optional[str] = Field(None, description="Groq API Key dự phòng, dùng khi GROQ_API_KEY lỗi")
    GEMINI_API_KEY: Optional[str] = Field(None, description="Google Gemini API Key")

    # 4. JWT & Auth Configuration
    JWT_SECRET_KEY: str = Field(..., description="Secret key for signing JWT tokens")
    JWT_ALGORITHM: str = Field("HS256", description="Algorithm for JWT signing")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(15, description="Access token lifespan in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(15, description="Refresh token lifespan in days")
    PASSWORD_RESET_EXPIRE_MINUTES: int = Field(10, description="Password reset token expiration in minutes")

    # 5. Cookie Configuration
    JWT_ACCESS_COOKIE_NAME: str = Field("access_token", description="Cookie name for access token")
    JWT_COOKIE_NAME: str = Field("refresh_token", description="Cookie name for refresh token")
    JWT_COOKIE_HTTPONLY: bool = Field(True, description="Enforce HttpOnly flag on auth cookies")
    JWT_COOKIE_SECURE: bool = Field(False, description="Enforce Secure flag on auth cookies (HTTPS only)")
    JWT_COOKIE_SAMESITE: str = Field("lax", description="SameSite policy: lax, strict, none")

    # 6. OTP Configuration
    OTP_EXPIRE_MINUTES: int = Field(5, description="OTP code lifespan in minutes")
    OTP_RESEND_COOLDOWN_SECONDS: int = Field(60, description="Cooldown between OTP requests in seconds")

    # 7. Google OAuth Keys
    GOOGLE_CLIENT_ID: Optional[str] = Field(None, description="Google OAuth Web Client ID")
    GOOGLE_IOS_CLIENT_ID: Optional[str] = Field(None, description="Google OAuth iOS Client ID")
    GOOGLE_WEB_CLIENT_ID: Optional[str] = Field(None, description="Google OAuth Web Client ID")
    GOOGLE_ANDROID_CLIENT_ID: Optional[str] = Field(None, description="Google OAuth Android Client ID")

    # 8. SMTP Email Configuration
    SMTP_HOST: Optional[str] = Field(None, description="SMTP server hostname")
    SMTP_PORT: int = Field(587, description="SMTP server port")
    SMTP_USERNAME: Optional[str] = Field(None, description="SMTP username/email")
    SMTP_PASSWORD: Optional[str] = Field(None, description="SMTP application password")
    SMTP_FROM_EMAIL: Optional[str] = Field(None, description="Sender email address")
    SMTP_FROM_NAME: str = Field("VoiceCashBook", description="Sender display name")

    # 9. Cloudinary Storage Configuration
    CLOUDINARY_NAME: Optional[str] = Field(None, description="Cloudinary cloud name")
    CLOUDINARY_API_KEY: Optional[str] = Field(None, description="Cloudinary API key")
    CLOUDINARY_API_SECRET: Optional[str] = Field(None, description="Cloudinary API secret")

    # 10. OCR hóa đơn (Vintern-1B-v3.5). Cần cài requirements-ocr.txt; tắt thì route trả 503
    OCR_ENABLED: bool = Field(True, description="Bật/tắt API OCR hóa đơn")
    OCR_MODEL_ID: str = Field("5CD-AI/Vintern-1B-v3_5", description="Model Hugging Face dùng để OCR")
    OCR_MAX_TILES: int = Field(2, description="Số ô 448x448 tối đa mỗi ảnh; nhỏ = nhanh hơn trên CPU")
    OCR_MAX_IMAGE_MB: int = Field(8, description="Dung lượng ảnh tối đa (MB)")
    OCR_RESTORE_DIACRITICS: bool = Field(True, description="Thêm dấu cho dòng hóa đơn in không dấu (qua Groq)")
    OCR_DEPS_DIR: str = Field(".ocr_deps", description="Thư mục cài riêng transformers 4.44.2 cho Vintern (tương đối với thư mục BE)")

    @property
    def is_production(self) -> bool:
        env_val = (self.ENVIRONMENT or self.APP_ENV or "").strip().lower()
        return env_val == "production"

    @property
    def cookie_secure(self) -> bool:
        """Enforces Secure=True if in production environment or explicitly enabled."""
        return self.is_production or bool(self.JWT_COOKIE_SECURE)

    @property
    def cors_origins_list(self) -> list[str]:
        """Returns parsed list of allowed CORS origins."""
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Global singleton instance
settings = Settings()
