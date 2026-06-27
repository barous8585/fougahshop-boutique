import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Category
from ..schemas import CategoryCreate, CategoryOut
from ..auth import get_admin
from typing import List

router = APIRouter(prefix="/categories", tags=["categories"])

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[éèêë]', 'e', text)
    text = re.sub(r'[ïî]', 'i', text)
    text = re.sub(r'[ôö]', 'o', text)
    text = re.sub(r'[üù]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip('-')

@router.get("/", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).filter(Category.actif == True).order_by(Category.ordre).all()

@router.get("/all", response_model=List[CategoryOut])
def list_all_categories(db: Session = Depends(get_db), _=Depends(get_admin)):
    return db.query(Category).order_by(Category.ordre).all()

@router.post("/", response_model=CategoryOut)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), _=Depends(get_admin)):
    slug = slugify(data.nom)
    if db.query(Category).filter(Category.slug == slug).first():
        slug = f"{slug}-{db.query(Category).count()}"
    cat = Category(**data.dict(), slug=slug)
    db.add(cat); db.commit(); db.refresh(cat)
    return cat

@router.put("/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, data: CategoryCreate, db: Session = Depends(get_db), _=Depends(get_admin)):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat: raise HTTPException(404, "Catégorie introuvable")
    for k, v in data.dict().items(): setattr(cat, k, v)
    db.commit(); db.refresh(cat)
    return cat

@router.delete("/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(get_admin)):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat: raise HTTPException(404, "Catégorie introuvable")
    cat.actif = False; db.commit()
    return {"ok": True}
