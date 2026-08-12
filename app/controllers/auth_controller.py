from sqlalchemy.orm import Session

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest
)

from app.services.auth_service import (
    register_user,
    login_user,
    get_current_user
)


def register_controller(
    request: RegisterRequest,
    db: Session
):
    return register_user(
        db=db,
        data=request
    )


def login_controller(
    request: LoginRequest,
    db: Session
):
    return login_user(
        db=db,
        data=request
    )


def me_controller(
    payload: dict,
    db: Session
):
    return get_current_user(
        db=db,
        payload=payload
    )