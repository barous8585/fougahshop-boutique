from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True)
    description = Column(String(255))
    image_url = Column(String(500))
    couleur = Column(String(20), default="#1A8C5F")
    icone = Column(String(10), default="🛍️")
    ordre = Column(Integer, default=0)
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, index=True)
    description = Column(Text)
    prix = Column(Float, nullable=False)          # FCFA
    prix_barre = Column(Float)                    # Prix barré (avant promo)
    stock = Column(Integer, default=0)
    images = Column(JSON, default=list)           # ["url1", "url2", ...]
    category_id = Column(Integer, ForeignKey("categories.id"))
    en_vedette = Column(Boolean, default=False)
    tags = Column(JSON, default=list)             # ["tag1", "tag2"]
    video_url = Column(String(500))
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    category = relationship("Category", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    ref = Column(String(30), unique=True, index=True)   # BTQ-YYYYMMDD-XXXX
    # Client
    client_nom = Column(String(100), nullable=False)
    client_phone = Column(String(30), nullable=False)
    client_email = Column(String(150))
    # Livraison
    pays = Column(String(50), nullable=False)
    pays_code = Column(String(5))
    ville = Column(String(100))
    adresse = Column(Text)
    # Financier
    total_fcfa = Column(Float, nullable=False)
    total_devise = Column(Float)
    devise = Column(String(10), default="FCFA")
    # État
    statut = Column(String(30), default="en_attente")
    # en_attente | payée | en_preparation | expédiée | livrée | annulée
    notes_admin = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    nom_snapshot = Column(String(200))    # snapshot au moment de commande
    image_snapshot = Column(String(500))
    prix_unitaire = Column(Float)
    quantite = Column(Integer, default=1)
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    provider = Column(String(30))            # kkiapay | geniuspay | whatsapp
    transaction_id = Column(String(200))
    montant = Column(Float)
    devise = Column(String(10))
    statut = Column(String(20), default="en_attente")  # en_attente | success | failed
    raw_response = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    order = relationship("Order", back_populates="payments")

class Setting(Base):
    __tablename__ = "settings"
    id    = Column(Integer, primary_key=True, index=True)
    key   = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text)
