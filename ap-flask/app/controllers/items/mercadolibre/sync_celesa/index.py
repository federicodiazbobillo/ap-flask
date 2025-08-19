# index.py — Único blueprint del módulo Sync Celesa
from flask import Blueprint

# ===== ÚNICO blueprint =====
sync_celesa_bp = Blueprint(
    "sync_celesa_bp",
    __name__,
    template_folder="app/templates/items/mercadolibre",
)

# ===== Constantes / Estado compartido =====
PAGE_SIZE = 50
BATCH_SIZE_DEFAULT = 100
NULL_SENTINEL = "__NULL__"
ISBN_MIN = 1000000000000
ISBN_MAX = 9999999999999

# Jobs en memoria (por proceso)
JOBS = {}  # job_id -> dict


# ===== Helper compartido: WHERE para el listado =====
def build_where_for_list(statuses_only, include_null, isbn_ok, stock_filter):
    """
    Devuelve (where_sql, params) para el listado principal.
    Aplica filtros de: status, nulos, ISBN y filtros de stock.
    """
    clauses = []
    params = []

    # status
    if statuses_only:
        placeholders = ",".join(["%s"] * len(statuses_only))
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses_only)

    # sin status
    if include_null:
        clauses.append("(status IS NULL OR status = '')")

    # ISBN
    if isbn_ok == 'valid':
        clauses.append("(isbn BETWEEN %s AND %s)")
        params.extend([ISBN_MIN, ISBN_MAX])
    elif isbn_ok == 'invalid':
        clauses.append("(isbn IS NULL OR isbn < %s OR isbn > %s)")
        params.extend([ISBN_MIN, ISBN_MAX])

    # Filtros de stock (exclusivos)
    if stock_filter == 'celesa_zero_ml_positive':
        # Celesa = 0 y ML ≥ 1
        clauses.append("(COALESCE(stock_celesa, 0) = 0 AND COALESCE(stock_idml, 0) >= 1)")
    elif stock_filter == 'celesa_positive_ml_zero':
        # Celesa > 0 y ML = 0
        clauses.append("(COALESCE(stock_celesa, 0) > 0 AND COALESCE(stock_idml, 0) = 0)")
    elif stock_filter == 'celesa_diff':
        # Celesa ≠ ML (tratando NULL≠NULL usando -1)
        clauses.append("(COALESCE(stock_celesa, -1) <> COALESCE(stock_idml, -1))")

    where_sql = " AND ".join(clauses) if clauses else "1=1"
    return where_sql, params


# ===== Importa submódulos para adjuntar rutas al blueprint =====
from . import condiciones_generales  # noqa: E402,F401
from . import manejo_de_stock        # noqa: E402,F401
