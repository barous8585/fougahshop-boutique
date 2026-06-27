import os
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Order, Product, Category
from ..schemas import AdminLogin, Token, AdminStats
from ..auth import create_token, get_admin

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "changeme123")

@router.post("/login", response_model=Token)
def login(data: AdminLogin):
    if data.username != ADMIN_USER or data.password != ADMIN_PASS:
        raise HTTPException(401, "Identifiants incorrects")
    token = create_token({"sub": data.username, "role": "admin"})
    return {"access_token": token}

@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db), _=Depends(get_admin)):
    today = date.today()
    total_cmd = db.query(Order).count()
    cmd_today = db.query(Order).filter(func.date(Order.created_at) == today).count()
    ca = db.query(func.sum(Order.total_fcfa)).filter(Order.statut == "payée").scalar() or 0
    produits_actifs = db.query(Product).filter(Product.actif == True).count()
    en_attente = db.query(Order).filter(Order.statut == "en_attente").count()
    return {
        "total_commandes": total_cmd,
        "commandes_aujourd_hui": cmd_today,
        "chiffre_affaires": ca,
        "produits_actifs": produits_actifs,
        "commandes_en_attente": en_attente
    }
