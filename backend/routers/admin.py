import os, time
from collections import defaultdict
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Order, Product, Category, Setting
from ..schemas import AdminLogin, Token, AdminStats
from ..auth import create_token, get_admin
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])

import logging as _log
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "")

if not ADMIN_PASS:
    ADMIN_PASS = "changeme123"
    _log.getLogger(__name__).warning(
        "ADMIN_PASSWORD non défini — utilisation du mot de passe par défaut. "
        "Définissez ADMIN_PASSWORD dans Render > Environment."
    )

# ── Rate limiting login ───────────────────────────────────────────
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

    # Comparaison en temps constant (protège contre timing attacks)
    import hmac as _hmac
    user_ok = _hmac.compare_digest(
        data.username.strip().lower(),
        ADMIN_USER.strip().lower()
    )
    pass_ok = _hmac.compare_digest(data.password, ADMIN_PASS)

    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    # Connexion réussie — réinitialiser le compteur pour cet IP
    _attempts[ip] = []

    token = create_token({"sub": data.username, "role": "admin"})
    return {"access_token": token}

# ── Stats ─────────────────────────────────────────────────────────
@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db), _=Depends(get_admin)):
    today = date.today()
    return {
        "total_commandes":        db.query(Order).count(),
        "commandes_aujourd_hui":  db.query(Order).filter(func.date(Order.created_at) == today).count(),
        "chiffre_affaires":       db.query(func.sum(Order.total_fcfa)).filter(Order.statut == "payée").scalar() or 0,
        "produits_actifs":        db.query(Product).filter(Product.actif == True).count(),
        "commandes_en_attente":   db.query(Order).filter(Order.statut == "en_attente").count(),
    }

# ── Helpers settings DB ───────────────────────────────────────────
DEFAULTS = {
    "whatsapp":      os.getenv("WHATSAPP_NUM", "+224XXXXXXXXX"),
    "boutique_nom":  "FougahShop Boutique",
    "promo_message": "Livraison partout en Afrique · Paiement Mobile Money · Support WhatsApp 7j/7",
    "promo_active":  "true",
}

def _get(db: Session, key: str) -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else DEFAULTS.get(key, "")

def _set(db: Session, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()

# ── Settings (lecture admin) ──────────────────────────────────────
@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _=Depends(get_admin)):
    return {
        "whatsapp":      _get(db, "whatsapp"),
        "boutique_nom":  _get(db, "boutique_nom"),
        "promo_message": _get(db, "promo_message"),
        "promo_active":  _get(db, "promo_active") == "true",
    }

class SettingsUpdate(BaseModel):
    whatsapp:      Optional[str]  = None
    boutique_nom:  Optional[str]  = None
    promo_message: Optional[str]  = None
    promo_active:  Optional[bool] = None

@router.put("/settings")
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db), _=Depends(get_admin)):
    if data.whatsapp      is not None: _set(db, "whatsapp",      data.whatsapp)
    if data.boutique_nom  is not None: _set(db, "boutique_nom",  data.boutique_nom)
    if data.promo_message is not None: _set(db, "promo_message", data.promo_message)
    if data.promo_active  is not None: _set(db, "promo_active",  "true" if data.promo_active else "false")
    return get_settings(db, _)

# ── Settings publics (lecture client) ────────────────────────────
@router.get("/settings/public")
def public_settings(db: Session = Depends(get_db)):
    return {
        "whatsapp":      _get(db, "whatsapp"),
        "promo_message": _get(db, "promo_message"),
        "promo_active":  _get(db, "promo_active") == "true",
    }

# ── Commandes admin ───────────────────────────────────────────────
from ..models import OrderItem
from ..schemas import OrderOut, OrderStatusUpdate

@router.get("/orders/all")
def all_orders(statut: Optional[str] = None, db: Session = Depends(get_db), _=Depends(get_admin)):
    q = db.query(Order)
    if statut: q = q.filter(Order.statut == statut)
    return q.order_by(Order.created_at.desc()).all()

@router.put("/orders/{order_id}/statut")
def update_statut(order_id: int, data: OrderStatusUpdate, db: Session = Depends(get_db), _=Depends(get_admin)):
    o = db.query(Order).filter(Order.id == order_id).first()
    if not o: raise HTTPException(404, "Commande introuvable")
    o.statut = data.statut
    if data.notes_admin: o.notes_admin = data.notes_admin
    db.commit()
    db.refresh(o)
    return o
