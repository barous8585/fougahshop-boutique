import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routers import categories, products, orders, payments, admin

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FougahShop Boutique API", version="1.0.0")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://boutique.fougahshop.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:5500"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

app.include_router(categories.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

@app.get("/")
def root():
    return {"service": "FougahShop Boutique API", "status": "online"}

@app.get("/health")
def health():
    return {"ok": True}
