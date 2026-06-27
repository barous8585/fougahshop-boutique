import re, math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
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

@router.get("/", response_model=ProductList)
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    vedette: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db)
):
    q = db.query(Product).filter(Product.actif == True)
    if category:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat: q = q.filter(Product.category_id == cat.id)
    if search:
        q = q.filter(Product.nom.ilike(f"%{search}%"))
    if vedette is not None:
        q = q.filter(Product.en_vedette == vedette)
    total = q.count()
    items = q.order_by(Product.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": math.ceil(total/per_page)}

@router.get("/{prod_id}", response_model=ProductOut)
def get_product(prod_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == prod_id, Product.actif == True).first()
    if not p: raise HTTPException(404, "Produit introuvable")
    return p

@router.post("/", response_model=ProductOut)
def create_product(data: ProductCreate, db: Session = Depends(get_db), _=Depends(get_admin)):
    slug = slugify(data.nom)
    if db.query(Product).filter(Product.slug == slug).first():
        slug = f"{slug}-{db.query(Product).count()}"
    p = Product(**data.dict(), slug=slug)
    db.add(p); db.commit(); db.refresh(p)
    return p

@router.put("/{prod_id}", response_model=ProductOut)
def update_product(prod_id: int, data: ProductCreate, db: Session = Depends(get_db), _=Depends(get_admin)):
    p = db.query(Product).filter(Product.id == prod_id).first()
    if not p: raise HTTPException(404, "Produit introuvable")
    for k, v in data.dict().items(): setattr(p, k, v)
    db.commit(); db.refresh(p)
    return p

@router.delete("/{prod_id}")
def delete_product(prod_id: int, db: Session = Depends(get_db), _=Depends(get_admin)):
    p = db.query(Product).filter(Product.id == prod_id).first()
    if not p: raise HTTPException(404, "Produit introuvable")
    p.actif = False; db.commit()
    return {"ok": True}
