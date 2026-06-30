import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from ..database import get_db
from ..models import Review, Order, OrderItem, Product
from ..schemas import ReviewCreate, ReviewOut, ReviewableCheck, ReviewableItem
from ..auth import get_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reviews", tags=["reviews"])


def _recalc_product_rating(db: Session, product_id: int):
    """Recalcule note_moyenne et nb_avis a partir des avis existants."""
    result = db.query(
        func.avg(Review.note), func.count(Review.id)
    ).filter(Review.product_id == product_id).first()
    moyenne, total = result[0] or 0.0, result[1] or 0
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.note_moyenne = round(float(moyenne), 2)
        product.nb_avis = total
        db.commit()


# ── Verifier quels articles d'une commande peuvent recevoir un avis ──
@router.get("/eligible/{order_ref}", response_model=ReviewableCheck)
def check_reviewable(order_ref: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.ref == order_ref).first()
    if not order:
        raise HTTPException(404, "Commande introuvable")

    items_out = []
    if order.statut == "livrée":
        already_reviewed = {
            r.product_id for r in db.query(Review).filter(Review.order_id == order.id).all()
        }
        for it in order.items:
            if it.product_id is None:
                continue
            items_out.append(ReviewableItem(
                product_id=it.product_id,
                nom=it.nom_snapshot,
                image=it.image_snapshot,
                deja_avis=it.product_id in already_reviewed
            ))

    return ReviewableCheck(order_ref=order.ref, statut=order.statut, items=items_out)


# ── Soumettre un avis (cote client, apres livraison) ──────────────
@router.post("/", response_model=ReviewOut)
def create_review(data: ReviewCreate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.ref == data.order_ref.strip().upper()).first()
    if not order:
        raise HTTPException(404, "Commande introuvable")
    if order.statut != "livrée":
        raise HTTPException(400, "Cette commande n'est pas encore livrée")

    # Verifier que le produit fait bien partie de cette commande
    item_match = next((i for i in order.items if i.product_id == data.product_id), None)
    if not item_match:
        raise HTTPException(400, "Ce produit ne fait pas partie de cette commande")

    # Empecher un double avis pour le meme produit + commande
    existing = db.query(Review).filter(
        Review.order_id == order.id,
        Review.product_id == data.product_id
    ).first()
    if existing:
        raise HTTPException(400, "Vous avez deja laisse un avis pour ce produit")

    if not (1 <= data.note <= 5):
        raise HTTPException(400, "La note doit etre comprise entre 1 et 5")

    review = Review(
        product_id=data.product_id,
        order_id=order.id,
        order_ref=order.ref,
        client_nom=data.client_nom.strip()[:100],
        note=data.note,
        commentaire=(data.commentaire or "").strip()[:1000] or None,
        photos=data.photos[:5],  # max 5 photos
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _recalc_product_rating(db, data.product_id)

    return review


# ── Avis publics d'un produit ──────────────────────────────────────
@router.get("/product/{product_id}", response_model=List[ReviewOut])
def list_product_reviews(product_id: int, page: int = 1, per_page: int = 10, db: Session = Depends(get_db)):
    return (db.query(Review)
              .filter(Review.product_id == product_id)
              .order_by(Review.created_at.desc())
              .offset((page - 1) * per_page)
              .limit(per_page)
              .all())


# ── Admin : liste complete + suppression (moderation legere) ──────
@router.get("/admin/all", response_model=List[ReviewOut])
def admin_list_reviews(page: int = 1, per_page: int = 30, db: Session = Depends(get_db), _=Depends(get_admin)):
    return (db.query(Review)
              .order_by(Review.created_at.desc())
              .offset((page - 1) * per_page)
              .limit(per_page)
              .all())


@router.delete("/admin/{review_id}")
def admin_delete_review(review_id: int, db: Session = Depends(get_db), _=Depends(get_admin)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, "Avis introuvable")
    product_id = review.product_id
    db.delete(review)
    db.commit()
    _recalc_product_rating(db, product_id)
    return {"ok": True}
