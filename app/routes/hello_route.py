from fastapi import APIRouter
from app.controllers.hello_controller import HelloController

router = APIRouter()


@router.get("/")
def hello():
    return HelloController.hello()