from fastapi import FastAPI

from app.routes.hello_route import router as hello_router
from app.routes.category_route import router as category_router
from app.routes.product_route import router as product_router

from app.configs.database import auth_db


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0"
)


@app.on_event("startup")
def startup():
    auth_db()


app.include_router(
    hello_router,
    prefix="/api/v1"
)


app.include_router(
    category_router,
    prefix="/api/v1"
)


app.include_router(
    product_router,
    prefix="/api/v1"
)


@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }