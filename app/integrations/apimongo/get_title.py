#get_title.py
import os
from typing import Optional, Dict, Any
from functools import lru_cache

import requests

# Config vía ENV (no hardcodear secretos)
APIMONGO_BASE_URL = os.getenv("APIMONGO_BASE_URL")
APIMONGO_TOKEN = os.getenv("APIMONGO_TOKEN")  


if not APIMONGO_BASE_URL or not APIMONGO_TOKEN:
    raise RuntimeError("Faltan APIMONGO_BASE_URL o APIMONGO_TOKEN en el entorno")

HEADERS = (
    {"Authorization": f"Bearer {APIMONGO_TOKEN}"} if APIMONGO_TOKEN else None
)

@lru_cache(maxsize=2048)
def get_title(isbn: str) -> Optional[str]:
    """
    Devuelve el TitleText (string) para el ISBN dado, o None si no existe/errores.
    Usa la API externa /api/titulo.
    """
    if not isbn:
        return None
    try:
        if not HEADERS:
            # Si falta token, no hacemos request
            return None

        url = f"{APIMONGO_BASE_URL}/api/titulo"
        resp = requests.get(url, headers=HEADERS, params={"isbn": isbn}, timeout=6)
        if resp.status_code != 200:
            return None

        data = resp.json()  # {"isbn":..., "candidatos":[...], "title":..., "matched":...}
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        return None
    except Exception:
        return None


def get_title_raw(isbn: str) -> Optional[Dict[str, Any]]:
    """
    Igual que get_title(), pero devuelve todo el JSON de la API (útil para debug puntual).
    """
    if not isbn:
        return None
    try:
        if not HEADERS:
            return None

        url = f"{APIMONGO_BASE_URL}/api/titulo"
        resp = requests.get(url, headers=HEADERS, params={"isbn": isbn}, timeout=6)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None
