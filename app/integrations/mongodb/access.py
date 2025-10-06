# app/integrations/mongodb/access.py
import os
import threading
from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError
import re

# --- Config desde ENV (con defaults) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB_CELESA = os.getenv("MONGO_DB_CELESA", "celesa")
MONGO_COLL_CELESA_STOCK = os.getenv("MONGO_COLL_CELESA_STOCK", "stock")
MONGO_COLL_PRODUCTOS = os.getenv("MONGO_COLL_PRODUCTOS", "productos")

# --- Singleton del cliente ---
__client_lock = threading.Lock()
__client: Optional[MongoClient] = None

def get_mongo_client() -> MongoClient:
    """Devuelve un MongoClient singleton (lazy)."""
    global __client
    if __client is None:
        with __client_lock:
            if __client is None:
                __client = MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=3000,  # 3s para fallar rápido si no conecta
                    connect=False,                  # lazy connect
                    tz_aware=True
                )
    return __client

# --- Helpers de acceso ---
def get_database(name: Optional[str] = None) -> Database:
    """Devuelve una base de datos. Por defecto, la de Celesa."""
    db_name = name or MONGO_DB_CELESA
    return get_mongo_client()[db_name]

def get_collection(db_name: str, coll_name: str) -> Collection:
    """Acceso genérico a cualquier colección."""
    return get_mongo_client()[db_name][coll_name]

def get_celesa_stock_collection() -> Collection:
    """Acceso directo a celesa.stock."""
    return get_collection(MONGO_DB_CELESA, MONGO_COLL_CELESA_STOCK)

def get_products_collection() -> Collection:
    """Acceso directo a celesa.productos."""
    return get_collection(MONGO_DB_CELESA, MONGO_COLL_PRODUCTOS)

# --- Utilidades ---
def ping_mongo() -> bool:
    """Verifica conectividad con el servidor MongoDB."""
    try:
        get_mongo_client().admin.command("ping")
        return True
    except Exception:
        return False

def ensure_indexes():
    """
    Crea índices mínimos recomendados.
    Llamar una sola vez en el arranque de la app (opcional).
    """
    try:
        # Índice por ISBN en 'stock' (si aplica en tu modelo)
        get_celesa_stock_collection().create_index(
            "isbn", name="idx_isbn", background=True
        )
    except Exception:
        pass

    try:
        # Índice por RecordReference en 'productos' (clave para getTitle)
        get_products_collection().create_index(
            "RecordReference", name="idx_record_reference", background=True
        )
    except Exception:
        pass

# --- API mínima reutilizable ---

def getTitle(record_reference: str) -> Optional[str]:
    """
    Busca TitleText probando estas variantes de clave:
      - RecordReference == code
      - RecordReference == code_sindigitos
      - ProductIdentifier.IDValue == cualquiera de las dos anteriores
    Devuelve el primer TitleText encontrado o None.
    """
    code = (str(record_reference).strip() if record_reference is not None else "")
    if not code:
        return None

    # Variante “solo dígitos” por si en Mongo guardaron sin guiones/espacios
    only_digits = re.sub(r"\D+", "", code)

    try:
        col = get_products_collection()
        proj = {
            "_id": 0,
            "DescriptiveDetail.TitleDetail.TitleElement.TitleText": 1,
        }

        query_codes = list({c for c in (code, only_digits) if c})
        if not query_codes:
            return None

        doc = col.find_one(
            {
                "$or": [
                    {"RecordReference": {"$in": query_codes}},
                    {"ProductIdentifier.IDValue": {"$in": query_codes}},
                ]
            },
            proj,
        )
        if not doc:
            return None

        te = (
            (doc.get("DescriptiveDetail") or {})
            .get("TitleDetail", {})
            .get("TitleElement")
        )

        if isinstance(te, list):
            for el in te:
                if isinstance(el, dict) and el.get("TitleText"):
                    return str(el["TitleText"]).strip()
            return None
        if isinstance(te, dict):
            tt = te.get("TitleText")
            return str(tt).strip() if tt else None
        return None
    except Exception:
        return None
    


def getTitle_debg(record_reference: str) -> Optional[dict]:
    """
    DEBUG: devuelve info de diagnóstico y (si existe) el documento crudo (sin _id)
    que matchea el código dado. No parsea TitleText ni nada.
    """
    code = (str(record_reference).strip() if record_reference is not None else "")
    if not code:
        return {
            "ok": True,
            "input": code,
            "keys": [],
            "env": {"db": MONGO_DB_CELESA, "coll": MONGO_COLL_PRODUCTOS, "uri_hint": MONGO_URI},
            "matched": 0,
            "doc": None,
        }

    only_digits = re.sub(r"\D+", "", code)
    keys = [k for k in {code, only_digits} if k]

    try:
        col = get_products_collection()
        q = {
            "$or": [
                {"RecordReference": {"$in": keys}},
                {"ProductIdentifier.IDValue": {"$in": keys}},
            ]
        }

        # Contar si hay match (sin escanear todo)
        matched = col.count_documents(q, limit=1)

        # Traer documento crudo (sin _id) SOLO si hay match
        doc = col.find_one(q, {"_id": 0}) if matched else None

        # Tratar de exponer a qué host/puerto se conectó realmente
        client = get_mongo_client()
        try:
            addr = getattr(client, "address", None)
            if not addr and hasattr(client, "nodes"):
                # PyMongo < 4 expone nodes como set de (host, port)
                nodes = getattr(client, "nodes", None)
                addr = list(nodes)[0] if nodes else None
        except Exception:
            addr = None

        return {
            "ok": True,
            "input": code,
            "keys": keys,
            "env": {
                "db": MONGO_DB_CELESA,
                "coll": MONGO_COLL_PRODUCTOS,
                "uri_hint": MONGO_URI,
                "connected_to": f"{addr[0]}:{addr[1]}" if addr else None,
            },
            "matched": int(matched),
            "doc": doc,
        }

    except PyMongoError as e:
        return {
            "ok": False,
            "input": code,
            "keys": keys,
            "env": {"db": MONGO_DB_CELESA, "coll": MONGO_COLL_PRODUCTOS, "uri_hint": MONGO_URI},
            "error": str(e),
            "matched": 0,
            "doc": None,
        }