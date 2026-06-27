from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime

# ── Categories ─────────────────────────────────────────────────
class CategoryBase(BaseModel):
    nom: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    couleur: str = "#1A8C5F"
    icone: str = "🛍️"
    ordre: int = 0
    actif: bool = True

class CategoryCreate(CategoryBase): pass

class CategoryOut(CategoryBase):
    id: int
    slug: str
    class Config: from_attributes = True

# ── Products ────────────────────────────────────────────────────
class ProductBase(BaseModel):
    nom: str
    description: Optional[str] = None
    prix: float
    prix_barre: Optional[float] = None
    stock: int = 0
    images: List[str] = []
    video_url: Optional[str] = None
    category_id: Optional[int] = None
    en_vedette: bool = False
    tags: List[str] = []
    actif: bool = True

class ProductCreate(ProductBase): pass

class ProductOut(ProductBase):
    id: int
    slug: str
    category: Optional[CategoryOut] = None
    created_at: datetime
    class Config: from_attributes = True

class ProductList(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    per_page: int
    pages: int

# ── Orders ──────────────────────────────────────────────────────
class OrderItemIn(BaseModel):
    product_id: int
    quantite: int = 1

class OrderCreate(BaseModel):
    client_nom: str
    client_phone: str
    client_email: Optional[str] = None
    pays: str
    pays_code: str
    ville: Optional[str] = None
    adresse: Optional[str] = None
    devise: str = "FCFA"
    items: List[OrderItemIn]

class OrderItemOut(BaseModel):
    id: int
    nom_snapshot: str
    image_snapshot: Optional[str]
    prix_unitaire: float
    quantite: int
    class Config: from_attributes = True

class OrderOut(BaseModel):
    id: int
    ref: str
    client_nom: str
    client_phone: str
    pays: str
    ville: Optional[str]
    total_fcfa: float
    total_devise: Optional[float]
    devise: str
    statut: str
    items: List[OrderItemOut]
    created_at: datetime
    class Config: from_attributes = True

# ── Payments ────────────────────────────────────────────────────
class KkiapayVerify(BaseModel):
    transaction_id: str
    order_ref: str

class PaymentOut(BaseModel):
    id: int
    provider: str
    statut: str
    montant: float
    class Config: from_attributes = True

# ── Admin ───────────────────────────────────────────────────────
class AdminLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class OrderStatusUpdate(BaseModel):
    statut: str
    notes_admin: Optional[str] = None

class AdminStats(BaseModel):
    total_commandes: int
    commandes_aujourd_hui: int
    chiffre_affaires: float
    produits_actifs: int
    commandes_en_attente: int
