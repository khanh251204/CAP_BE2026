from fastapi import FastAPI

from app.routes.hello_route import router as hello_router
from app.routes.category_route import router as category_router
from app.routes.auth_route import router as auth_router
from app.routes.customer_route import router as customer_router
from app.routes.supplier_route import router as supplier_router

from app.configs.database import auth_db


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0"
)


# STARTUP
@app.on_event("startup")
def startup():
    auth_db()


# ROUTERS
app.include_router(
    hello_router,
    prefix="/api/v1"
)

app.include_router(
    category_router,
    prefix="/api/v1"
)

app.include_router(
    auth_router
)

app.include_router(
    customer_router
)

app.include_router(
    supplier_router
)


# ROOT
@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }