# app/integrations/mongodb/access.py
import os
import threading
from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

# --- Config desde ENV (con defaults) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_CELESA = os.getenv("MONGO_DB_CELESA", "celesa")
MONGO_COLL_CELESA_STOCK = os.getenv("MONGO_COLL_CELESA_STOCK", "stock")

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
    col = get_celesa_stock_collection()
    # Índice por ISBN (si no existe). unique según tu modelo.
    col.create_index("isbn", name="idx_isbn", background=True)
