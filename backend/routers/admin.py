import os, time
from collections import defaultdict
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Order, Product, Category
from ..schemas import AdminLogin, Token, AdminStats
from ..auth import create_token, get_admin

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "changeme123")

# ── Rate limiting login (5 essais / 5 minutes par IP) ────────────
_attempts: dict = defaultdict(list)

def _check_rate(ip: str):
    now = time.time()
    window = [t for t in _attempts[ip] if now - t < 300]
    _attempts[ip] = window
    if len(window) >= 5:
        raise HTTPException(429, "Trop de tentatives. Réessayez dans 5 minutes.")
    _attempts[ip].append(now)

# ── Login ─────────────────────────────────────────────────────────
@router.post("/login", response_model=Token)
def login(data: AdminLogin, request: Request):
    ip = request.client.host if request.client else "unknown"
    _check_rate(ip)
    if data.username != ADMIN_USER or data.password != ADMIN_PASS:
        raise HTTPException(401, "Identifiants incorrects")
    # Reset tentatives si succès
    _attempts[ip] = []
    token = create_token({"sub": data.username, "role": "admin"})
    return {"access_token": token}

# ── Stats ─────────────────────────────────────────────────────────
@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db), _=Depends(get_admin)):
    today = date.today()
    total_cmd  = db.query(Order).count()
    cmd_today  = db.query(Order).filter(func.date(Order.created_at) == today).count()
    ca         = db.query(func.sum(Order.total_fcfa)).filter(Order.statut == "payée").scalar() or 0
    prods      = db.query(Product).filter(Product.actif == True).count()
    en_attente = db.query(Order).filter(Order.statut == "en_attente").count()
    return {
        "total_commandes": total_cmd,
        "commandes_aujourd_hui": cmd_today,
        "chiffre_affaires": ca,
        "produits_actifs": prods,
        "commandes_en_attente": en_attente
    }

# ── Settings (numéro WhatsApp + config boutique) ──────────────────
_settings: dict = {
    "whatsapp": os.getenv("WHATSAPP_NUM", "+224XXXXXXXXX"),
    "boutique_nom": "FougahShop Boutique",
    "promo_message": "Livraison partout en Afrique · Paiement Mobile Money",
    "promo_active": True,
}

from pydantic import BaseModel
from typing import Optional

class SettingsUpdate(BaseModel):
    whatsapp: Optional[str] = None
    boutique_nom: Optional[str] = None
    promo_message: Optional[str] = None
    promo_active: Optional[bool] = None

@router.get("/settings")
def get_settings(_=Depends(get_admin)):
    return _settings

@router.put("/settings")
def update_settings(data: SettingsUpdate, _=Depends(get_admin)):
    if data.whatsapp is not None:
        _settings["whatsapp"] = data.whatsapp
    if data.boutique_nom is not None:
        _settings["boutique_nom"] = data.boutique_nom
    if data.promo_message is not None:
        _settings["promo_message"] = data.promo_message
    if data.promo_active is not None:
        _settings["promo_active"] = data.promo_active
    return _settings

# ── Endpoint public pour lire les settings (WhatsApp visible client) ──
@router.get("/settings/public")
def public_settings():
    return {
        "whatsapp": _settings["whatsapp"],
        "promo_message": _settings["promo_message"],
        "promo_active": _settings["promo_active"],
    }
