import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from ..database import get_db
from ..auth import get_admin

router = APIRouter(prefix="/admin/settings", tags=["settings"])

# ── Clés publiques autorisées (pas de données sensibles) ─────────
PUBLIC_KEYS = {"whatsapp", "whatsapp_boutique", "promo_message", "promo_active"}


# ── Modèle Setting ────────────────────────────────────────────────
# (doit exister dans models.py — créé ici si absent)
def get_or_create_setting(db: Session, key: str, default: str = "") -> str:
    try:
        from ..models import Setting
        row = db.query(Setting).filter(Setting.key == key).first()
        return row.value if row else default
    except Exception:
        return default


def set_setting(db: Session, key: str, value: str):
    try:
        from ..models import Setting
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
            db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


# ── GET /admin/settings ───────────────────────────────────────────
@router.get("/")
async def get_settings(
    db: Session = Depends(get_db),
    _: str = Depends(get_admin)
):
    """Retourne tous les paramètres (admin seulement)."""
    try:
        from ..models import Setting
        rows = db.query(Setting).all()
        return {row.key: row.value for row in rows}
    except Exception:
        return {}


# ── GET /admin/settings/public ────────────────────────────────────
@router.get("/public")
async def get_public_settings(db: Session = Depends(get_db)):
    """
    Paramètres publics — aucune authentification requise.
    Retourne uniquement les clés autorisées (pas de données sensibles).
    """
    try:
        from ..models import Setting
        rows = db.query(Setting).filter(Setting.key.in_(PUBLIC_KEYS)).all()
        result = {row.key: row.value for row in rows}
        # Convertir promo_active en booléen
        if "promo_active" in result:
            result["promo_active"] = result["promo_active"].lower() in ("true", "1", "yes")
        return result
    except Exception:
        # Table absente ou autre erreur → retourner dict vide (gracieux)
        return {}


# ── PUT /admin/settings/{key} ─────────────────────────────────────
@router.put("/{key}")
async def update_setting(
    key: str,
    body: dict,
    db: Session = Depends(get_db),
    _: str = Depends(get_admin)
):
    """Met à jour un paramètre (admin seulement)."""
    value = body.get("value", "")
    if value is None:
        raise HTTPException(400, "Valeur manquante")

    # Limites
    if len(key) > 100:
        raise HTTPException(400, "Clé trop longue")
    if len(str(value)) > 5000:
        raise HTTPException(400, "Valeur trop longue")

    try:
        set_setting(db, key, str(value))
        return {"ok": True, "key": key, "value": str(value)}
    except Exception as e:
        raise HTTPException(500, f"Erreur sauvegarde : {e}")


# ── GET /admin/settings/{key} ─────────────────────────────────────
@router.get("/{key}")
async def get_setting(
    key: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_admin)
):
    """Retourne un paramètre précis (admin seulement)."""
    value = get_or_create_setting(db, key)
    return {"key": key, "value": value}


# ── Initialisation des paramètres par défaut ─────────────────────
async def init_default_settings(db: Session):
    """
    Appelé au démarrage depuis main.py pour créer la table et
    les valeurs par défaut si elles n'existent pas encore.
    """
    defaults = {
        "whatsapp":         os.getenv("WHATSAPP_NUM", "+224XXXXXXXXX"),
        "whatsapp_boutique": os.getenv("WHATSAPP_BOUTIQUE", "+224XXXXXXXXX"),
        "promo_message":    "🎉 Livraison offerte dès 50€ d'achat !",
        "promo_active":     "false",
    }
    try:
        from ..models import Setting
        for key, default in defaults.items():
            existing = db.query(Setting).filter(Setting.key == key).first()
            if not existing:
                db.add(Setting(key=key, value=default))
        db.commit()
    except Exception:
        db.rollback()
