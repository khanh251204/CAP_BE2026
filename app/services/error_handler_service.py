from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder


class ErrorHandlerService:
    """
    Service tập trung xử lý và định dạng các lỗi / ngoại lệ (Exception Handlers)
    cho hệ thống API, đảm bảo trả về cấu trúc JSON chuẩn mực và status code chính xác.
    """

    @staticmethod
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Xử lý lỗi RequestValidationError từ Pydantic / FastAPI schema validation,
        trả về HTTP 422 Unprocessable Entity kèm chi tiết các trường dữ liệu vi phạm.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({
                "status": "error",
                "success": False,
                "message": "Dữ liệu không hợp lệ",
                "detail": exc.errors()
            })
        )

    @classmethod
    def register_exception_handlers(cls, app: FastAPI) -> None:
        """
        Đăng ký toàn bộ exception handlers vào FastAPI application instance.
        """
        app.add_exception_handler(RequestValidationError, cls.validation_exception_handler)
