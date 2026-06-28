"""
Proxy d'upload vers Cloudinary.
Contourne les restrictions CSP/CORS du navigateur.
Le frontend envoie le fichier au backend Render,
le backend le transfère à Cloudinary et retourne l'URL.
"""
import os
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from ..auth import get_admin

router = APIRouter(prefix="/upload", tags=["upload"])

CLOUD_NAME   = os.getenv("CLOUDINARY_CLOUD_NAME",   "dw45o1sok")
CLOUD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET", "boutique_media")


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    resource_type: str = Form(default="image"),
    _=Depends(get_admin)
):
    """Transfère le fichier vers Cloudinary et retourne l'URL."""
    # Lire le contenu
    content = await file.read()

    if not content:
        raise HTTPException(400, "Fichier vide")

    # Limites de taille
    max_size = 100 * 1024 * 1024 if resource_type == "video" else 10 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(400, f"Fichier trop lourd (max {'100' if resource_type=='video' else '10'} Mo)")

    # Envoyer à Cloudinary
    cloudinary_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/{resource_type}/upload"

    try:
        resp = requests.post(
            cloudinary_url,
            data={"upload_preset": CLOUD_PRESET},
            files={"file": (file.filename, content, file.content_type)},
            timeout=120
        )
    except requests.exceptions.Timeout:
        raise HTTPException(504, "Timeout — Cloudinary trop lent")
    except requests.exceptions.RequestException as e:
        raise HTTPException(503, f"Connexion Cloudinary impossible : {str(e)}")

    # Parser la réponse
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(502, f"Réponse invalide de Cloudinary (status {resp.status_code})")

    if "secure_url" in data:
        return {
            "url":       data["secure_url"],
            "public_id": data.get("public_id", ""),
            "format":    data.get("format", ""),
            "width":     data.get("width"),
            "height":    data.get("height"),
        }
    elif "error" in data:
        raise HTTPException(400, data["error"].get("message", "Erreur Cloudinary"))
    else:
        raise HTTPException(502, "Réponse Cloudinary inattendue")
