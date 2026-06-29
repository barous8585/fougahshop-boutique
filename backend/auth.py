import os
import jwt
import logging
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET", "")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "4"))  # 4h = cohérent avec le frontend

if not SECRET_KEY:
    import secrets
    SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "⚠️  SECRET_KEY non défini en variable d'environnement. "
        "Un token aléatoire est utilisé — tous les tokens seront "
        "invalidés au redémarrage du serveur. "
        "Définissez SECRET_KEY dans Render > Environment."
    )

bearer = HTTPBearer(auto_error=False)  # auto_error=False pour un message d'erreur personnalisé


# ── Création du token ─────────────────────────────────────────────
def create_token(data: dict) -> str:
    """
    Crée un JWT signé.
    Utilise timezone.utc (datetime.utcnow() est déprécié depuis Python 3.12).
    """
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iat": now,                                          # issued at
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),   # expiration
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── Vérification du token ─────────────────────────────────────────
def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """
    Vérifie le token JWT dans le header Authorization: Bearer <token>.
    Lève 401 si absent, invalide ou expiré.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat"]},  # champs obligatoires
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré — reconnectez-vous",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide : {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dépendance admin ──────────────────────────────────────────────
def get_admin(payload: dict = Depends(verify_token)) -> dict:
    """
    Vérifie que le token appartient à un admin.
    Lève 403 si le rôle est absent ou incorrect.
    """
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return payload


# ── Endpoint login (à utiliser dans admin.py ou main.py) ─────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")  # OBLIGATOIRE en production

def check_admin_credentials(username: str, password: str) -> bool:
    """
    Vérifie les identifiants admin.
    Compare de façon constante (protège contre les timing attacks).
    """
    import hmac
    if not ADMIN_PASSWORD:
        logger.error("ADMIN_PASSWORD non défini — connexion admin bloquée")
        return False
    user_ok = hmac.compare_digest(username.strip(), ADMIN_USERNAME)
    pass_ok = hmac.compare_digest(password, ADMIN_PASSWORD)
    return user_ok and pass_ok
