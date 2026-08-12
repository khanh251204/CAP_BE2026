from fastapi import (
    APIRouter,
    Depends,
    status
)

from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authenticate_user

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest
)

from app.controllers.auth_controller import (
    register_controller,
    login_controller,
    me_controller
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

# REGISTER
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    return register_controller(
        request=request,
        db=db
    )

# LOGIN
@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    return login_controller(
        request=request,
        db=db
    )

# CURRENT USER
@router.get("/me")
def me(
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(get_db)
):
    return me_controller(
        payload=payload,
        db=db
    )