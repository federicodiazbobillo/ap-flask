# manejo_de_stock.py — Rutas específicas de “Manejo de stock”
from flask import request, redirect, url_for, jsonify

# Igual que arriba: no expongas el blueprint como global
def _bp():
    from .index import sync_celesa_bp
    return sync_celesa_bp


# --- Utilidad interna: redirigir al índice con un stock_filter dado ---
_ALLOWED_STOCK_FILTERS = {
    "celesa_zero_ml_positive",  # Celesa = 0  y ML ≥ 1
    "celesa_positive_ml_zero",  # Celesa > 0  y ML = 0
    "celesa_diff",              # Celesa ≠ ML
}

def _redirect_with_stock_filter(stock_filter_value: str):
    """
    Arma una redirección al listado principal con tab=stock y el stock_filter indicado.
    Preserva parámetros existentes (status, isbn_ok, etc.), normaliza page=1.
    """
    if stock_filter_value not in _ALLOWED_STOCK_FILTERS:
        # fallback seguro: sin filtro de stock
        params = request.args.to_dict(flat=False)
        params["tab"] = ["stock"]
        params["page"] = ["1"]
        return redirect(url_for('sync_celesa_bp.index', **params), code=302)

    params = request.args.to_dict(flat=False)  # preserva repetidos
    params["tab"] = ["stock"]
    params["stock_filter"] = [stock_filter_value]
    params["page"] = ["1"]
    return redirect(url_for('sync_celesa_bp.index', **params), code=302)


# --- Atajos de UI / compatibilidad ---
@_bp().route('/sync_celesa/stock_mismatch')
def stock_mismatch():
    """
    LEGACY: Lista ítems donde stock_celesa = 0 y stock_idml >= 1.
    Redirige al listado principal activando la pestaña 'stock'
    y aplicando ese filtro especial.
    """
    return _redirect_with_stock_filter("celesa_zero_ml_positive")


@_bp().route('/sync_celesa/stock_celesa_positive_ml_zero')
def stock_celesa_positive_ml_zero():
    """
    Atajo: Celesa > 0 y ML = 0.
    """
    return _redirect_with_stock_filter("celesa_positive_ml_zero")


@_bp().route('/sync_celesa/stock_diff')
def stock_diff():
    """
    Atajo: Celesa ≠ ML.
    """
    return _redirect_with_stock_filter("celesa_diff")


@_bp().route('/sync_celesa/stock_filter/<key>')
def stock_filter_key(key):
    """
    Endpoint genérico: /sync_celesa/stock_filter/<key>
    Acepta únicamente los valores permitidos en _ALLOWED_STOCK_FILTERS.
    """
    if key not in _ALLOWED_STOCK_FILTERS:
        return jsonify({
            "error": "invalid_stock_filter",
            "allowed": sorted(list(_ALLOWED_STOCK_FILTERS)),
        }), 400
    return _redirect_with_stock_filter(key)


# (Opcional) Placeholders antiguos — dejarlos si pensás usarlos más adelante,
# o eliminarlos si ya no se necesitan en la UI.
@_bp().route('/sync_celesa/stock_push_start', methods=['POST'])
def stock_push_start():
    return jsonify({
        "error": "not_implemented",
        "message": "Push de stock Celesa → ML pendiente de implementar"
    }), 501


@_bp().route('/sync_celesa/stock_pull_start', methods=['POST'])
def stock_pull_start():
    return jsonify({
        "error": "not_implemented",
        "message": "Pull de stock ML → DB pendiente de implementar"
    }), 501


@_bp().route('/sync_celesa/stock_sync_start', methods=['POST'])
def stock_sync_start():
    return jsonify({
        "error": "not_implemented",
        "message": "Sync de diferencias (Celesa → ML) pendiente de implementar"
    }), 501
