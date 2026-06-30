import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import PromoCode
from ..schemas import (
    PromoCodeCreate, PromoCodeOut,
    PromoValidateRequest, PromoValidateResponse
)
from ..auth import get_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/promos", tags=["promos"])


# ── Validation publique (utilisee dans le checkout) ───────────────
@router.post("/validate", response_model=PromoValidateResponse)
def validate_promo(data: PromoValidateRequest, db: Session = Depends(get_db)):
    code_clean = data.code.strip().upper()
    promo = db.query(PromoCode).filter(PromoCode.code == code_clean).first()

    if not promo:
        return PromoValidateResponse(valid=False, message="Code promo introuvable")
    if not promo.actif:
        return PromoValidateResponse(valid=False, message="Ce code promo n'est plus actif")

    now = datetime.now(timezone.utc)
    if promo.date_expiration and promo.date_expiration < now:
        return PromoValidateResponse(valid=False, message="Ce code promo a expire")
    if promo.usage_max is not None and promo.usage_count >= promo.usage_max:
        return PromoValidateResponse(valid=False, message="Ce code promo a atteint sa limite d'utilisation")

    if promo.type == "percent":
        reduction = round(data.total_fcfa * (promo.valeur / 100), 2)
    else:
        reduction = min(promo.valeur, data.total_fcfa)

    nouveau_total = max(0.0, data.total_fcfa - reduction)

    return PromoValidateResponse(
        valid=True,
        message=f"Code applique : -{promo.valeur}{'%' if promo.type=='percent' else ' FCFA'}",
        code=promo.code,
        type=promo.type,
        valeur=promo.valeur,
        reduction_fcfa=reduction,
        nouveau_total_fcfa=nouveau_total,
    )


# ── Admin : CRUD codes promo ───────────────────────────────────────
@router.get("/admin/all", response_model=List[PromoCodeOut])
def admin_list_promos(db: Session = Depends(get_db), _=Depends(get_admin)):
    return db.query(PromoCode).order_by(PromoCode.created_at.desc()).all()


@router.post("/admin/", response_model=PromoCodeOut)
def admin_create_promo(data: PromoCodeCreate, db: Session = Depends(get_db), _=Depends(get_admin)):
    code_clean = data.code.strip().upper()
    if not code_clean:
        raise HTTPException(400, "Le code ne peut pas etre vide")
    if data.type not in ("percent", "fixed"):
        raise HTTPException(400, "Type invalide (percent ou fixed)")
    if data.valeur <= 0:
        raise HTTPException(400, "La valeur doit etre positive")

    existing = db.query(PromoCode).filter(PromoCode.code == code_clean).first()
    if existing:
        raise HTTPException(400, "Ce code existe deja")

    promo = PromoCode(
        code=code_clean,
        type=data.type,
        valeur=data.valeur,
        actif=data.actif,
        date_expiration=data.date_expiration,
        usage_max=data.usage_max,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


@router.put("/admin/{promo_id}/toggle", response_model=PromoCodeOut)
def admin_toggle_promo(promo_id: int, db: Session = Depends(get_db), _=Depends(get_admin)):
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(404, "Code promo introuvable")
    promo.actif = not promo.actif
    db.commit()
    db.refresh(promo)
    return promo


@router.delete("/admin/{promo_id}")
def admin_delete_promo(promo_id: int, db: Session = Depends(get_db), _=Depends(get_admin)):
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(404, "Code promo introuvable")
    db.delete(promo)
    db.commit()
    return {"ok": True}
