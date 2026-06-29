import os, hmac, hashlib, logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Order, Payment
from ..schemas import KkiapayVerify
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

KKIAPAY_PRIVATE_KEY = os.getenv("KKIAPAY_PRIVATE_KEY", "")
KKIAPAY_SECRET      = os.getenv("KKIAPAY_SECRET", "")
GENIUSPAY_SECRET    = os.getenv("GENIUSPAY_SECRET_KEY", "")

# Taux de conversion EUR → devises (doit rester cohérent avec le frontend)
TAUX_EUR_FCFA = int(os.getenv("TAUX_EUR_FCFA", "700"))   # 1 EUR = 700 FCFA
TAUX_EUR_GNF  = int(os.getenv("TAUX_EUR_GNF",  "10800"))  # 1 EUR = 10800 GNF


def fcfa_to_gnf(montant_fcfa: float) -> int:
    """Convertit un montant FCFA en GNF via l'EUR comme pivot."""
    eur = montant_fcfa / TAUX_EUR_FCFA
    return int(round(eur * TAUX_EUR_GNF))


# ──────────────────────────────────────────────────────────────
# KKIAPAY : vérification post-paiement (appelé par le frontend)
# ──────────────────────────────────────────────────────────────
@router.post("/kkiapay/verify")
async def kkiapay_verify(data: KkiapayVerify, db: Session = Depends(get_db)):
    """
    Le widget Kkiapay retourne un transaction_id côté client.
    On vérifie côté serveur via l'API Kkiapay avant de valider.
    """
    order = db.query(Order).filter(Order.ref == data.order_ref).first()
    if not order:
        raise HTTPException(404, "Commande introuvable")

    if order.statut == "payée":
        return {"ok": True, "ref": order.ref, "already_paid": True}

    if not KKIAPAY_PRIVATE_KEY:
        raise HTTPException(500, "Clé privée Kkiapay manquante (variable KKIAPAY_PRIVATE_KEY)")

    # Vérifier la transaction via l'API Kkiapay
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.kkiapay.me/api/v1/transactions/{data.transaction_id}/status",
                headers={"x-private-key": KKIAPAY_PRIVATE_KEY}
            )
        tx = resp.json()
    except Exception as e:
        logger.error(f"[kkiapay_verify] Erreur API Kkiapay: {e}")
        raise HTTPException(502, f"Impossible de vérifier le paiement Kkiapay : {e}")

    if tx.get("status") != "SUCCESS":
        raise HTTPException(400, f"Paiement non confirmé (statut : {tx.get('status', 'inconnu')})")

    # Enregistrer le paiement
    pmt = Payment(
        order_id=order.id,
        provider="kkiapay",
        transaction_id=data.transaction_id,
        montant=order.total_fcfa,
        devise=order.devise or "XOF",
        statut="success",
        raw_response=tx
    )
    db.add(pmt)
    order.statut = "payée"
    db.commit()

    logger.info(f"[kkiapay_verify] Commande {order.ref} payée via Kkiapay ✓")
    return {"ok": True, "ref": order.ref}


# ──────────────────────────────────────────────────────────────
# KKIAPAY : webhook serveur (événements asynchrones)
# ──────────────────────────────────────────────────────────────
@router.post("/kkiapay/webhook")
async def kkiapay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig  = request.headers.get("x-kkiapay-signature", "")

    # Vérification HMAC (uniquement si la clé est configurée)
    if KKIAPAY_SECRET:
        expected = hmac.new(
            KKIAPAY_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(400, "Signature webhook invalide")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Payload JSON invalide")

    if payload.get("status") == "SUCCESS":
        order_ref = (
            payload.get("metadata", {}).get("order_ref")
            or payload.get("order_ref")
        )
        if order_ref:
            order = db.query(Order).filter(Order.ref == order_ref).first()
            if order and order.statut == "en_attente":
                pmt = Payment(
                    order_id=order.id,
                    provider="kkiapay",
                    transaction_id=payload.get("transactionId") or payload.get("transaction_id"),
                    montant=payload.get("amount") or order.total_fcfa,
                    devise=order.devise or "XOF",
                    statut="success",
                    raw_response=payload
                )
                db.add(pmt)
                order.statut = "payée"
                db.commit()
                logger.info(f"[kkiapay_webhook] Commande {order_ref} payée ✓")

    return {"received": True}


# ──────────────────────────────────────────────────────────────
# GENIUS PAY : webhook serveur
# ──────────────────────────────────────────────────────────────
@router.post("/geniuspay/webhook")
async def geniuspay_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Payload JSON invalide")

    # Vérification HMAC optionnelle (adapter selon la doc Genius Pay)
    if GENIUSPAY_SECRET:
        body = await request.body()
        sig  = request.headers.get("x-genius-signature", "")
        expected = hmac.new(
            GENIUSPAY_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if sig and not hmac.compare_digest(sig, expected):
            raise HTTPException(400, "Signature Genius Pay invalide")

    statut_ok = payload.get("status") in ("SUCCESS", "PAID", "success", "paid")
    order_ref = payload.get("order_id") or payload.get("reference") or payload.get("order_ref")

    if statut_ok and order_ref:
        order = db.query(Order).filter(Order.ref == order_ref).first()
        if order and order.statut == "en_attente":
            # Montant : Genius Pay travaille en GNF pour la Guinée
            montant_gnf = payload.get("amount") or fcfa_to_gnf(order.total_fcfa)

            pmt = Payment(
                order_id=order.id,
                provider="geniuspay",
                transaction_id=str(payload.get("transaction_id") or payload.get("id") or ""),
                montant=montant_gnf,
                devise="GNF",
                statut="success",
                raw_response=payload
            )
            db.add(pmt)
            order.statut = "payée"
            db.commit()
            logger.info(f"[geniuspay_webhook] Commande {order_ref} payée en GNF ✓")

    return {"received": True}


# ──────────────────────────────────────────────────────────────
# UTILITAIRE : montant à envoyer à Kkiapay/Genius Pay
# ──────────────────────────────────────────────────────────────
@router.get("/amount/{order_ref}")
async def get_payment_amount(order_ref: str, db: Session = Depends(get_db)):
    """
    Retourne le montant à envoyer au widget de paiement.
    - Kkiapay reçoit le montant en FCFA (XOF)
    - Genius Pay reçoit le montant en GNF
    """
    order = db.query(Order).filter(Order.ref == order_ref).first()
    if not order:
        raise HTTPException(404, "Commande introuvable")

    devise = order.devise or "XOF"
    fcfa   = order.total_fcfa or 0

    if devise == "GNF":
        montant_paiement = fcfa_to_gnf(fcfa)
        provider = "geniuspay"
    else:
        montant_paiement = int(fcfa)
        provider = "kkiapay"

    return {
        "ref":               order.ref,
        "provider":          provider,
        "devise":            devise,
        "montant_paiement":  montant_paiement,   # montant brut pour le widget
        "total_fcfa":        fcfa,
        "taux_eur_fcfa":     TAUX_EUR_FCFA,
    }
