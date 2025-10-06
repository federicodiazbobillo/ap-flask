# app/controllers/items/mercadolibre/sync_celesa/index.py
from flask import Blueprint, redirect, url_for, request


# ===== ÚNICO blueprint =====
sync_celesa_bp = Blueprint(
    "sync_celesa_bp",
    __name__,
    url_prefix="/sync-celesa",   # << clave para /sync-celesa/...
    # sin template_folder: usamos rutas absolutas desde /templates
)

# ===== Constantes / Estado compartido =====
PAGE_SIZE = 50
BATCH_SIZE_DEFAULT = 100
NULL_SENTINEL = "__NULL__"
ISBN_MIN = 1000000000000
ISBN_MAX = 9999999999999

# Jobs en memoria (por proceso)
JOBS = {}  # job_id -> dict

# ===== Home de Sync Celesa =====
@sync_celesa_bp.route("/", methods=["GET"])
def index():
    # Redirige preservando los query params (page, status, isbn_ok, tab, etc.)
    params = request.args.to_dict(flat=False)
    return redirect(url_for("sync_celesa_bp.sync_celesa_list", **params), code=302)

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
        clauses.append("(COALESCE(stock_celesa, 0) = 0 AND COALESCE(stock_idml, 0) >= 1)")
    elif stock_filter == 'celesa_positive_ml_zero':
        clauses.append("(COALESCE(stock_celesa, 0) > 0 AND COALESCE(stock_idml, 0) = 0)")
    elif stock_filter == 'celesa_diff':
        clauses.append("""
            (COALESCE(stock_celesa, 0) > 0)
            AND (COALESCE(stock_idml, 0) > 0)
            AND (COALESCE(stock_celesa, 0) <> COALESCE(stock_idml, 0))
        """)

    where_sql = " AND ".join(clauses) if clauses else "1=1"
    return where_sql, params

# ===== Importa submódulos para adjuntar rutas al blueprint =====
from . import condiciones_generales  # noqa: E402,F401
from . import manejo_de_stock        # noqa: E402,F401
from . import parametros_sale_terms_celesa  # <<< añade este import
from . import api_ops  # noqa: E402,F401