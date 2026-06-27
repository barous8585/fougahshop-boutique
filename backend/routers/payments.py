import os, hmac, hashlib, httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Order, Payment
from ..schemas import KkiapayVerify
from ..auth import get_admin

router = APIRouter(prefix="/payments", tags=["payments"])

KKIAPAY_PRIVATE_KEY = os.getenv("KKIAPAY_PRIVATE_KEY", "")
KKIAPAY_SECRET = os.getenv("KKIAPAY_SECRET", "")
GENIUSPAY_SECRET = os.getenv("GENIUSPAY_SECRET_KEY", "")

# ── Kkiapay : vérification post-paiement côté client ────────────
@router.post("/kkiapay/verify")
async def kkiapay_verify(data: KkiapayVerify, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.ref == data.order_ref).first()
    if not order: raise HTTPException(404, "Commande introuvable")

    # Vérifier la transaction via l'API Kkiapay
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.kkiapay.me/api/v1/transactions/{data.transaction_id}/status",
            headers={"x-private-key": KKIAPAY_PRIVATE_KEY}
        )
    tx = resp.json()

    if tx.get("status") != "SUCCESS":
        raise HTTPException(400, f"Paiement non confirmé: {tx.get('status')}")

    # Enregistrer le paiement
    pmt = Payment(
        order_id=order.id, provider="kkiapay",
        transaction_id=data.transaction_id,
        montant=order.total_fcfa, devise="FCFA",
        statut="success", raw_response=tx
    )
    db.add(pmt)
    order.statut = "payée"
    db.commit()
    return {"ok": True, "ref": order.ref}

# ── Kkiapay : webhook serveur ────────────────────────────────────
@router.post("/kkiapay/webhook")
async def kkiapay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("x-kkiapay-signature", "")
    expected = hmac.new(KKIAPAY_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(400, "Signature invalide")
    payload = await request.json()
    if payload.get("status") == "SUCCESS":
        # Trouver la commande via metadata
        order_ref = payload.get("metadata", {}).get("order_ref")
        if order_ref:
            order = db.query(Order).filter(Order.ref == order_ref).first()
            if order and order.statut == "en_attente":
                pmt = Payment(
                    order_id=order.id, provider="kkiapay",
                    transaction_id=payload.get("transactionId"),
                    montant=payload.get("amount"), devise="FCFA",
                    statut="success", raw_response=payload
                )
                db.add(pmt)
                order.statut = "payée"
                db.commit()
    return {"received": True}

# ── Genius Pay : webhook serveur ─────────────────────────────────
@router.post("/geniuspay/webhook")
async def geniuspay_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    # Vérification HMAC (adapter selon doc Genius Pay)
    order_ref = payload.get("order_id") or payload.get("reference")
    if payload.get("status") in ("SUCCESS", "PAID") and order_ref:
        order = db.query(Order).filter(Order.ref == order_ref).first()
        if order and order.statut == "en_attente":
            pmt = Payment(
                order_id=order.id, provider="geniuspay",
                transaction_id=str(payload.get("transaction_id")),
                montant=order.total_devise, devise=order.devise,
                statut="success", raw_response=payload
            )
            db.add(pmt)
            order.statut = "payée"
            db.commit()
    return {"received": True}
