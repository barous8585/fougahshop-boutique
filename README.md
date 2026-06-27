# FougahShop Boutique

Boutique dropshipping — `boutique.fougahshop.com`  
Distincte du service proxy FougahShop principal.

---

## Stack
- **Frontend** : HTML monolithique PWA → Netlify
- **Backend**  : FastAPI + PostgreSQL → Render
- **Paiements**: Kkiapay (FCFA) + Genius Pay (GNF) + WhatsApp fallback

## Déploiement

### 1. Backend (Render)
```bash
# Nouveau service Web Render → Python 3.11
# Start command :
uvicorn backend.main:app --host 0.0.0.0 --port $PORT

# Variables d'environnement à configurer sur Render :
DATABASE_URL=postgresql://...
SECRET_KEY=...
ADMIN_USER=admin
ADMIN_PASSWORD=...
FRONTEND_URL=https://boutique.fougahshop.com
KKIAPAY_PUBLIC_KEY=...
KKIAPAY_PRIVATE_KEY=...
KKIAPAY_SECRET=...
GENIUSPAY_SECRET_KEY=...
```

### 2. Frontend (Netlify)
```
# Dossier à déployer : racine du repo (index.html + manifest.json + netlify.toml + _headers)
# Modifier dans index.html (lignes CONFIG) :
const API_URL       = "https://ton-backend.onrender.com";
const KKIAPAY_PK    = "ta_cle_publique_kkiapay";
const GENIUSPAY_URL = "https://secure.geniuspay.net/pay";
const WHATSAPP_NUM  = "+224XXXXXXXXX";
```

### 3. Sous-domaine (Namecheap)
```
CNAME  boutique  →  [ton-site].netlify.app
```
Puis ajouter `boutique.fougahshop.com` dans Netlify → Domain settings.

### 4. Webhooks (après déploiement)
- Kkiapay dashboard → Webhook URL : `https://ton-backend.onrender.com/api/payments/kkiapay/webhook`
- Genius Pay → `https://ton-backend.onrender.com/api/payments/geniuspay/webhook`

---

## Structure

```
fougahshop-boutique/
├── index.html          ← Toute la boutique (SPA PWA)
├── manifest.json
├── netlify.toml
├── _headers            ← CSP Kkiapay
└── backend/
    ├── main.py
    ├── database.py
    ├── models.py
    ├── schemas.py
    ├── auth.py
    ├── requirements.txt
    ├── .env.example
    └── routers/
        ├── categories.py
        ├── products.py
        ├── orders.py
        ├── payments.py
        └── admin.py
```

## Pages frontend
| Page | URL hash | Description |
|---|---|---|
| Accueil | `#home` | Hero + catégories + vedettes |
| Catalogue | `#catalogue` | Grille + filtres + recherche |
| Produit | `#product` | Détail + galerie + ajout panier |
| Panier | `#panier` | Récap + quantités |
| Checkout | `#checkout` | Formulaire livraison |
| Paiement | `#paiement` | Kkiapay / Genius Pay / WhatsApp |
| Confirmation | `#confirmation` | Commande validée |
| Suivi | `#suivi` | Tracker par référence |
| Admin | `#admin` | Dashboard complet |

## Référence commande
Format : `BTQ-YYYYMMDD-XXXX` (ex: BTQ-20250715-A3K2)

## Pays supportés
- **Kkiapay (FCFA)** : Bénin, Togo, Côte d'Ivoire, Sénégal, Mali, Burkina Faso, Niger, Guinée-Bissau, Cameroun, Gabon, Congo-Brazza
- **Genius Pay (GNF)** : Guinée Conakry (×14 FCFA→GNF)
- **WhatsApp** : Tous les autres pays africains
