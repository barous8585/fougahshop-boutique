import re, math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from ..database import get_db
from ..models import Product, Category
from ..schemas import ProductCreate, ProductOut, ProductList
from ..auth import get_admin
from typing import Optional

router = APIRouter(prefix="/products", tags=["products"])

def slugify(text: str) -> str:
    text = text.lower().strip()
    for src, dst in [('àáâã','a'),('éèêë','e'),('ïî','i'),('ôö','o'),('üù','u'),('ç','c')]:
        for c in src: text = text.replace(c, dst)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip('-')

def product_to_dict(data: ProductCreate) -> dict:
    """Compatible Pydantic v1 et v2"""
    try:
        return data.model_dump()
    except AttributeError:
        return data.dict()

def safe_dict(d: dict, model) -> dict:
    """
    Filtre le dict pour ne garder que les colonnes
    qui existent réellement dans la table DB.
    Évite les erreurs si video_url ou autre colonne
    n'a pas encore été migrée.
    """
    try:
        valid = {c.key for c in inspect(model).mapper.column_attrs}
    except Exception:
        valid = {c.name for c in model.__table__.columns}
    return {k: v for k, v in d.items() if k in valid}

# ── GET liste ────────────────────────────────────────────────────
@router.get("/", response_model=ProductList)
def list_products(
    category: Optional[str] = None,
    search:   Optional[str] = None,
    vedette:  Optional[bool] = None,
    sort:     Optional[str] = None,   # "desc" (defaut), "price_asc", "price_desc"
    page:     int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db)
):
    q = db.query(Product).filter(Product.actif == True)
    if category:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            q = q.filter(Product.category_id == cat.id)
    if search:
        q = q.filter(Product.nom.ilike(f"%{search}%"))
    if vedette is not None:
        q = q.filter(Product.en_vedette == vedette)

    total = q.count()

    if sort == "price_asc":
        q = q.order_by(Product.prix.asc())
    elif sort == "price_desc":
        q = q.order_by(Product.prix.desc())
    else:
        q = q.order_by(Product.id.desc())

    items = (q.offset((page - 1) * per_page)
              .limit(per_page)
              .all())
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total else 1
    }

# ── GET un produit ───────────────────────────────────────────────
@router.get("/{prod_id}", response_model=ProductOut)
def get_product(prod_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(
        Product.id == prod_id,
        Product.actif == True
    ).first()
    if not p:
        raise HTTPException(404, "Produit introuvable")
    return p

# ── POST créer ───────────────────────────────────────────────────
@router.post("/", response_model=ProductOut)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin)
):
    d = product_to_dict(data)

    # Slug unique
    slug = slugify(d.get('nom', ''))
    if db.query(Product).filter(Product.slug == slug).first():
        slug = f"{slug}-{db.query(Product).count() + 1}"
    d['slug'] = slug

    # Images : toujours une liste
    if not d.get('images'):
        d['images'] = []

    # Filtrer colonnes existantes (sécurité migration)
    d = safe_dict(d, Product)

    p = Product(**d)
    db.add(p)
    try:
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erreur lors de la création : {str(e)}")
    return p

# ── PUT modifier ─────────────────────────────────────────────────
@router.put("/{prod_id}", response_model=ProductOut)
def update_product(
    prod_id: int,
    data: ProductCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin)
):
    p = db.query(Product).filter(Product.id == prod_id).first()
    if not p:
        raise HTTPException(404, "Produit introuvable")

    d = product_to_dict(data)

    # Images : toujours une liste
    if not d.get('images'):
        d['images'] = []

    # Filtrer colonnes existantes
    d = safe_dict(d, Product)

    for k, v in d.items():
        setattr(p, k, v)

    try:
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erreur lors de la mise à jour : {str(e)}")
    return p

# ── DELETE (soft) ────────────────────────────────────────────────
@router.delete("/{prod_id}")
def delete_product(
    prod_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin)
):
    p = db.query(Product).filter(Product.id == prod_id).first()
    if not p:
        raise HTTPException(404, "Produit introuvable")
    p.actif = False
    db.commit()
    return {"ok": True}
