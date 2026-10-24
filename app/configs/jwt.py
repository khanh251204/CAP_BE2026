import os
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Union
from dotenv import load_dotenv

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError

from app.configs.cookie import JWT_ACCESS_COOKIE_NAME
from app.configs.settings import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
PASSWORD_RESET_EXPIRE_MINUTES = settings.PASSWORD_RESET_EXPIRE_MINUTES

bearer_scheme = HTTPBearer(auto_error=False)


# ==============================================================================
# 1. CRYPTO & FINGERPRINT
# ==============================================================================

def create_password_fingerprint(password_hash: Optional[str]) -> str:
    """Tạo mã băm fingerprint từ mật khẩu băm để hủy bỏ reset token khi đổi mật khẩu."""
    raw = password_hash or ""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ==============================================================================
# 2. ACCESS TOKEN
# ==============================================================================

def create_access_token(data: dict) -> str:
    """Tạo JWT Access Token cho phiên đăng nhập."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Giải mã và xác thực JWT Access Token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access" or not payload.get("sub"):
            from app.services.system_log_service import log_event
            log_event(
                level="WARNING",
                step="AUTH",
                message="JWT token invalid payload structure",
                detail={"error": "Missing access type or sub claim"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ"
            )
        return payload
    except ExpiredSignatureError:
        from app.services.system_log_service import log_event
        log_event(
            level="WARNING",
            step="AUTH",
            message="JWT token expired",
            detail={"error": "ExpiredSignatureError"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn"
        )
    except JWTError as exc:
        from app.services.system_log_service import log_event
        log_event(
            level="WARNING",
            step="AUTH",
            message=f"JWT token decode error: {str(exc)}",
            detail={"error": str(exc), "error_type": type(exc).__name__}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )


# ==============================================================================
# 3. PASSWORD RESET TOKEN
# ==============================================================================

def create_reset_token(user_id: int, email: str, password_hash: str) -> str:
    """Tạo JWT Token đặt lại mật khẩu với thời hạn ngắn."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    password_fingerprint = create_password_fingerprint(password_hash)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "password_reset",
        "passwordFingerprint": password_fingerprint,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_reset_token(token: str) -> dict:
    """Giải mã và xác thực Password Reset Token."""
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    clean_token = token.strip().strip('"\'')
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()

    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    try:
        payload = jwt.decode(clean_token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("type")
        if token_type == "access":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token được cung cấp là Access Token. Vui lòng sử dụng API đổi mật khẩu (/change-password) khi đã đăng nhập."
            )
        if token_type != "password_reset" or not payload.get("sub") or not payload.get("email") or not payload.get("passwordFingerprint"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token không hợp lệ"
            )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token đã hết hạn"
        )
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )


# ==============================================================================
# 4. FASTAPI AUTHENTICATION & AUTHORIZATION DEPENDENCIES
# ==============================================================================

def authenticate_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> dict:
    """
    Xác thực người dùng từ Cookie (ưu tiên) hoặc Header Authorization Bearer.
    Trả về payload claims của JWT token.
    """
    token = request.cookies.get(JWT_ACCESS_COOKIE_NAME)
    if not token and credentials:
        token = credentials.credentials
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn chưa đăng nhập"
        )

    return decode_access_token(token)


def _load_access(user: dict):
    """Lấy role & quyền hiện tại của user từ DB (không tin claim 'role' trong token)."""
    from app.services.permission_service import PermissionService

    access = PermissionService.get_user_access(int(user.get("sub", 0)))
    if not access.exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc phiên đăng nhập đã hết hạn"
        )
    if access.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị tạm khóa. Vui lòng liên hệ quản trị viên."
        )
    return access


def authorize_roles(*roles):
    """
    Phân quyền theo Role người dùng (OWNER, STAFF, ADMIN, ...), đọc role hiện tại từ DB.
    Ưu tiên dùng require_permission để Admin có thể cấu hình quyền trên ma trận RBAC.
    """
    allowed = {str(r).strip().upper() for r in roles}

    def wrapper(user=Depends(authenticate_user)):
        if _load_access(user).role_name not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập"
            )
        return user

    return wrapper


def require_permission(permission_code: str):
    """
    Kiểm tra người dùng có quyền cụ thể (permission_code) hay không.
    ADMIN luôn có toàn quyền bỏ qua kiểm tra mã lẻ.
    """
    from app.configs.permissions import PERMISSION_CODES

    if permission_code not in PERMISSION_CODES:
        # Lỗi lập trình: phát hiện ngay lúc import thay vì 403 khó hiểu lúc chạy
        raise ValueError(f"Mã quyền '{permission_code}' chưa được khai báo trong app/configs/permissions.py")

    def wrapper(user=Depends(authenticate_user)):
        if not _load_access(user).has(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bạn không có quyền '{permission_code}' để thực hiện hành động này"
            )
        return user

    wrapper.permission_code = permission_code  # dùng cho test / kiểm tra độ phủ quyền
    return wrapper


ADMIN_PERMISSION_PREFIXES = ("admin_", "system:", "rbac:")


def require_admin_area(user=Depends(authenticate_user)):
    """
    Chặn ở cấp router cho khu vực /admin: chỉ cho qua ADMIN hoặc role có ít nhất một quyền quản trị.
    Từng endpoint vẫn phải kiểm tra quyền cụ thể bằng require_permission.
    """
    access = _load_access(user)
    if not (access.is_admin or any(p.startswith(ADMIN_PERMISSION_PREFIXES) for p in access.permissions)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập khu vực quản trị"
        )
    return user


def get_current_user_id(payload: dict = Depends(authenticate_user)) -> int:
    """Lấy user_id của người dùng hiện tại từ JWT token."""
    return int(payload["sub"])


def get_current_user_business_type(payload: dict = Depends(authenticate_user)) -> Optional[str]:
    """Lấy business_type (RESELLER, PRODUCER, SERVICE) từ JWT hoặc truy vấn DB."""
    bt = payload.get("business_type")
    if bt:
        return str(bt).strip().upper()
    try:
        from app.configs.database import SessionLocal
        from app.models.user_model import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == int(payload["sub"])).first()
            if user and user.business_type:
                return str(user.business_type).strip().upper()
        finally:
            db.close()
    except Exception:
        pass
    return None


def get_current_user_claims(payload: dict = Depends(authenticate_user)) -> dict:
    """Lấy toàn bộ claims định danh người dùng: user_id, email, role, business_type."""
    bt = payload.get("business_type")
    if not bt:
        try:
            from app.configs.database import SessionLocal
            from app.models.user_model import User
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.user_id == int(payload["sub"])).first()
                if user and user.business_type:
                    bt = str(user.business_type).strip().upper()
            finally:
                db.close()
        except Exception:
            pass

    return {
        "user_id": int(payload["sub"]),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "business_type": bt
    }


def get_current_user_id_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[int]:
    """
    Lấy user_id nếu có token hợp lệ, nếu chưa đăng nhập hoặc token sai thì trả về None
    thay vì quăng lỗi 401 (thích hợp cho các endpoint công khai có hỗ trợ nhận diện user).
    """
    try:
        token = request.cookies.get(JWT_ACCESS_COOKIE_NAME)
        if not token and credentials:
            token = credentials.credentials
        if not token:
            return None
        payload = decode_access_token(token)
        return int(payload["sub"])
    except Exception:
        return None


__all__ = [
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "PASSWORD_RESET_EXPIRE_MINUTES",
    "bearer_scheme",
    "create_password_fingerprint",
    "create_access_token",
    "decode_access_token",
    "create_reset_token",
    "decode_reset_token",
    "authenticate_user",
    "authorize_roles",
    "require_permission",
    "require_admin_area",
    "get_current_user_id",
    "get_current_user_id_optional",
    "get_current_user_business_type",
    "get_current_user_claims",
]
