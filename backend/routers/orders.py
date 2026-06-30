import random, string
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Order, OrderItem, Product, PromoCode
from ..schemas import OrderCreate, OrderOut, OrderStatusUpdate
from ..auth import get_admin
from typing import List

router = APIRouter(prefix="/orders", tags=["orders"])

def gen_ref() -> str:
    date = datetime.now().strftime("%Y%m%d")
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BTQ-{date}-{suffix}"

TAUX_GNF = 14  # 1 FCFA = 14 GNF

@router.post("/", response_model=OrderOut)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    # Vérifier les produits + calculer le total
    total_fcfa = 0.0
    items_data = []
    for item_in in data.items:
        p = db.query(Product).filter(Product.id == item_in.product_id, Product.actif == True).first()
        if not p: raise HTTPException(404, f"Produit {item_in.product_id} introuvable")
        if p.stock < item_in.quantite:
            raise HTTPException(400, f"Stock insuffisant pour '{p.nom}' (dispo: {p.stock})")
        total_fcfa += p.prix * item_in.quantite
        items_data.append((p, item_in.quantite))

    # ── Code promo (optionnel) ──────────────────────────────────
    reduction_fcfa = 0.0
    promo_applied = None
    promo_obj = None
    if data.promo_code:
        code_clean = data.promo_code.strip().upper()
        promo_obj = db.query(PromoCode).filter(
            PromoCode.code == code_clean,
            PromoCode.actif == True
        ).first()
        if promo_obj:
            now = datetime.now(timezone.utc)
            expired = promo_obj.date_expiration and promo_obj.date_expiration < now
            exhausted = promo_obj.usage_max is not None and promo_obj.usage_count >= promo_obj.usage_max
            if not expired and not exhausted:
                if promo_obj.type == "percent":
                    reduction_fcfa = round(total_fcfa * (promo_obj.valeur / 100), 2)
                else:
                    reduction_fcfa = min(promo_obj.valeur, total_fcfa)
                promo_applied = promo_obj.code

    total_fcfa_final = max(0.0, total_fcfa - reduction_fcfa)

    # Conversion devise (sur le total APRES reduction)
    total_devise = total_fcfa_final
    devise = data.devise
    if data.pays_code == "GN":
        total_devise = total_fcfa_final * TAUX_GNF
        devise = "GNF"
    else:
        devise = "FCFA"

    # Créer la commande
    order = Order(
        ref=gen_ref(),
        client_nom=data.client_nom,
        client_phone=data.client_phone,
        client_email=data.client_email,
        pays=data.pays, pays_code=data.pays_code,
        ville=data.ville, adresse=data.adresse,
        total_fcfa=total_fcfa_final, total_devise=total_devise, devise=devise,
        promo_code=promo_applied, reduction_fcfa=reduction_fcfa
    )
    db.add(order); db.flush()

    # Incrementer l'usage du code promo seulement si la commande est creee avec succes
    if promo_obj and promo_applied:
        promo_obj.usage_count += 1

    # Créer les lignes + décrémenter stock
    for p, qty in items_data:
        item = OrderItem(
            order_id=order.id, product_id=p.id,
            nom_snapshot=p.nom,
            image_snapshot=p.images[0] if p.images else None,
            prix_unitaire=p.prix, quantite=qty
        )
        db.add(item)
        p.stock -= qty

    db.commit(); db.refresh(order)
    return order

@router.get("/track/{ref}", response_model=OrderOut)
def track_order(ref: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.ref == ref).first()
    if not order: raise HTTPException(404, "Commande introuvable")
    return order

# ── Admin ────────────────────────────────────────────────────────
@router.get("/admin/all", response_model=List[OrderOut])
def admin_list_orders(
    statut: str = None,
    page: int = 1, per_page: int = 20,
    db: Session = Depends(get_db), _=Depends(get_admin)
):
    q = db.query(Order)
    if statut: q = q.filter(Order.statut == statut)
    return q.order_by(Order.id.desc()).offset((page-1)*per_page).limit(per_page).all()

@router.put("/admin/{order_id}/statut", response_model=OrderOut)
def update_statut(order_id: int, data: OrderStatusUpdate, db: Session = Depends(get_db), _=Depends(get_admin)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order: raise HTTPException(404, "Commande introuvable")
    order.statut = data.statut
    if data.notes_admin: order.notes_admin = data.notes_admin
    db.commit(); db.refresh(order)
    return order
