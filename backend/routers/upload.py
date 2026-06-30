"""
Proxy d'upload vers Cloudinary.
Le backend reçoit le fichier depuis le frontend et le transfère
à Cloudinary — contourne les restrictions CSP/CORS du navigateur.
"""
import os
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from ..auth import get_admin

router = APIRouter(prefix="/upload", tags=["upload"])

CLOUD_NAME   = os.getenv("CLOUDINARY_CLOUD_NAME",   "dw45o1sok")
CLOUD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET", "boutique_media")

# Formats image supportés par Cloudinary
IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif",
    "image/webp", "image/bmp", "image/tiff", "image/tif",
    "image/heic", "image/heif", "image/x-heic",
    "image/avif", "image/svg+xml", "image/ico", "image/x-ico",
    "image/psd", "image/vnd.adobe.photoshop",
}

VIDEO_TYPES = {
    "video/mp4", "video/webm", "video/quicktime",
    "video/x-msvideo", "video/avi", "video/mpeg",
}


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    resource_type: str = Form(default="image"),
    _=Depends(get_admin)
):
    """
    Transfère le fichier vers Cloudinary et retourne l'URL.
    Compatible avec tous les formats image courants.
    """
    content = await file.read()

    if not content:
        raise HTTPException(400, "Fichier vide reçu")

    # Taille maximale
    max_size = 100 * 1024 * 1024 if resource_type == "video" else 10 * 1024 * 1024
    if len(content) > max_size:
        mb = "100" if resource_type == "video" else "10"
        raise HTTPException(400, f"Fichier trop lourd (max {mb} Mo)")

    # Détecter le bon resource_type selon le MIME
    content_type = file.content_type or ""
    if content_type in VIDEO_TYPES:
        resource_type = "video"
    elif content_type in IMAGE_TYPES or content_type.startswith("image/"):
        resource_type = "image"
    # Si type inconnu, on garde ce que le client a envoyé

    # Upload vers Cloudinary
    cloudinary_url = (
        f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/{resource_type}/upload"
    )

    try:
        resp = requests.post(
            cloudinary_url,
            data={"upload_preset": CLOUD_PRESET},
            files={"file": (file.filename, content, content_type or "application/octet-stream")},
            timeout=120,
        )
    except requests.exceptions.Timeout:
        raise HTTPException(504, "Timeout — Cloudinary trop lent, réessaie")
    except requests.exceptions.RequestException as e:
        raise HTTPException(503, f"Connexion Cloudinary impossible : {str(e)}")

    # Parser la réponse
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(502, f"Réponse invalide de Cloudinary (HTTP {resp.status_code})")

    if "secure_url" in data:
        return {
            "url":       data["secure_url"],
            "public_id": data.get("public_id", ""),
            "format":    data.get("format", ""),
            "width":     data.get("width"),
            "height":    data.get("height"),
        }
    elif "error" in data:
        msg = data["error"].get("message", "Erreur Cloudinary inconnue")
        raise HTTPException(400, f"Cloudinary : {msg}")
    else:
        raise HTTPException(502, f"Réponse Cloudinary inattendue : {data}")

@router.post("/review-photo")
async def upload_review_photo(file: UploadFile = File(...)):
    """
    Upload PUBLIC reserve aux photos d'avis client (pas d'auth admin requise).
    Restrictions plus strictes : images uniquement, 5 Mo max.
    """
    content = await file.read()

    if not content:
        raise HTTPException(400, "Fichier vide recu")

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "Photo trop lourde (max 5 Mo)")

    content_type = file.content_type or ""
    if not (content_type in IMAGE_TYPES or content_type.startswith("image/")):
        raise HTTPException(400, "Seules les images sont acceptees pour un avis")

    cloudinary_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    try:
        resp = requests.post(
            cloudinary_url,
            data={"upload_preset": CLOUD_PRESET, "folder": "avis_clients"},
            files={"file": (file.filename, content, content_type or "application/octet-stream")},
            timeout=60,
        )
    except requests.exceptions.Timeout:
        raise HTTPException(504, "Timeout upload photo")
    except requests.exceptions.RequestException as e:
        raise HTTPException(503, f"Connexion impossible : {str(e)}")

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(502, "Reponse invalide de Cloudinary")

    if "secure_url" in data:
        return {"url": data["secure_url"]}
    elif "error" in data:
        raise HTTPException(400, f"Cloudinary : {data['error'].get('message', 'erreur inconnue')}")
    else:
        raise HTTPException(502, "Reponse Cloudinary inattendue")
