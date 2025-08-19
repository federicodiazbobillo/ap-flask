# app/controllers/items/mercadolibre/sync_celesa/api_ops.py
import time
from typing import Optional, Tuple, Dict, Any

import requests
from flask import request, jsonify

# Traer el blueprint sin exponerlo globalmente
def _bp():
    from .index import sync_celesa_bp
    return sync_celesa_bp

# Token (opcional) del sistema
try:
    # verificar_meli() -> (access_token, user_id, error)
    from app.integrations.mercadolibre.services.token_service import verificar_meli
except Exception:
    verificar_meli = None

# DB
from app.db import get_conn

# Regla de sale terms por stock
from .parametros_sale_terms_celesa import get_sale_term_for_stock


# -------------------- Helpers token / headers --------------------
def _prefer_token_header() -> Dict[str, str]:
    """Devuelve Authorization Bearer si hay token válido; si no, {}."""
    if not verificar_meli:
        return {}
    try:
        access_token, user_id, error = verificar_meli()
        if error or not access_token:
            return {}
        return {"Authorization": f"Bearer {access_token}"}
    except Exception:
        return {}


def _check_token_valid() -> Tuple[bool, Optional[Dict[str, Any]], Optional[int]]:
    """
    Llama a /users/me con el Bearer actual.
    - (True, user_json, 200) si ok
    - (False, {"error":...}, status) si inválido o falla
    """
    headers = _prefer_token_header()
    if not headers:
        return False, {"error": "token_missing"}, 401
    try:
        r = requests.get("https://api.mercadolibre.com/users/me", headers=headers, timeout=10)
        if r.status_code == 200:
            return True, r.json(), 200
        # 401/403/expired/etc
        return False, {"error": "token_invalid", "status": r.status_code}, r.status_code
    except Exception as e:
        return False, {"error": f"token_check_failed: {type(e).__name__}"}, 0


# -------------------- Helpers ML --------------------
def _ml_get_item(idml: str, timeout: int = 15) -> Tuple[Optional[Dict], int]:
    """GET /items/{id} con Bearer (reintenta sin header si 401/403)."""
    url = f"https://api.mercadolibre.com/items/{idml}"
    headers = _prefer_token_header()
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code in (401, 403) and headers:
            # Reintento sin header por si aplica
            r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json(), 200
        return None, r.status_code
    except Exception:
        return None, 0  # error de red


def _ml_get_item_backoff(idml: str, max_retries: int = 5) -> Tuple[Optional[Dict], int]:
    """Backoff simple para 429/50x."""
    tries = 0
    while True:
        js, code = _ml_get_item(idml)
        if code in (429, 500, 502, 503) and tries < max_retries:
            time.sleep(1.0)
            tries += 1
            continue
        return js, code


# -------------------- Helpers negocio --------------------
def _is_full(item_json: Dict) -> bool:
    """Detecta FULL por shipping.logistic_type == 'fulfillment'."""
    shipping = (item_json or {}).get("shipping") or {}
    return (shipping.get("logistic_type") or "").lower() == "fulfillment"


def _status_allows_update(status: Optional[str]) -> bool:
    """Sólo se permite actualizar si el estado es active o paused."""
    return (status or "").lower() in ("active", "paused")


def _get_stock_celesa(idml: str) -> Optional[int]:
    """Lee stock_celesa desde items_meli. Devuelve int o None si no hay dato."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT stock_celesa FROM items_meli WHERE idml=%s", (idml,))
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])
    except Exception:
        return None
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _build_sale_terms_for(stock: int) -> list:
    """
    Arma sale_terms según tabla sale_terms_celesa. Si no hay regla:
      - si stock == 0 => 35
      - si stock  > 0 => 20
    """
    rule = get_sale_term_for_stock(stock, provider='celesa') or {}
    dias = None
    try:
        dias = int(rule.get("delivery_days"))
    except Exception:
        pass

    if dias is None:
        dias = 35 if (stock or 0) == 0 else 20

    return [
        {"id": "MANUFACTURING_TIME", "value_name": f"{dias} días"},
        {"id": "WARRANTY_TIME", "value_name": "90 días"},
        {"id": "WARRANTY_TYPE", "value_id": "2230279"},
    ]


def _build_put_payload(stock: int) -> Dict[str, Any]:
    """Payload exacto acordado."""
    status = "active" if (stock or 0) > 0 else "paused"
    return {
        "available_quantity": int(stock),
        "status": status,
        "sale_terms": _build_sale_terms_for(int(stock)),
    }


# -------------------- API: bulk_put (1x1) --------------------
@_bp().route('/bulk-put', methods=['POST'], endpoint='bulk_put')
def bulk_put():
    """
    Espera JSON:
      - { "id": "MLA123" }  (preferido)
      - o { "ids": ["MLA123"] } (compat)
      - opcional: { "emulate": true } para no hacer PUT real

    Flujo:
      1) Verifica token con /users/me → si falla: 401 {"error":"token_invalid"}
      2) GET /items/{id}
         - !=200 → {"id":..., "result": "GET:<code>"}
      3) Si FULL → {"id":..., "result": "full"}
      4) Si status no es active/paused → {"id":..., "result": "<status>"}
      5) Lee stock_celesa → si None → {"id":..., "result": "NO_STOCK"}
      6) Arma payload y hace PUT (o emula con sleep)
         → {"id":..., "result": <http_code>}
    """
    data = request.get_json(silent=True) or {}

    # Resolver ID (id o ids[0])
    idml = (data.get("id") or "").strip()
    if not idml:
        ids = data.get("ids") or []
        if isinstance(ids, list) and ids:
            try:
                idml = str(ids[0]).strip()
            except Exception:
                idml = ""
    if not idml:
        return jsonify({"error": "id_required"}), 400

    emulate = bool(data.get("emulate", False))

    # 1) Check token una vez por request
    ok_token, token_info, token_status = _check_token_valid()
    if not ok_token:
        # Responder 401/403/etc para que el front muestre "401" (en lugar de 500)
        return jsonify(token_info or {"error": "token_invalid"}), (token_status or 401)

    # 2) GET del ítem
    js, code = _ml_get_item_backoff(idml)
    if code != 200:
        return jsonify({"id": idml, "result": f"GET:{code}"}), 200

    # 3) FULL
    if _is_full(js or {}):
        return jsonify({"id": idml, "result": "full"}), 200

    # 4) Estado permitido para actualizar
    api_status = (js or {}).get("status")
    if not _status_allows_update(api_status):
        return jsonify({"id": idml, "result": str(api_status or "UNKNOWN")}), 200

    # 5) Stock Celesa desde DB (sin default a 0)
    stock = _get_stock_celesa(idml)
    if stock is None:
        return jsonify({"id": idml, "result": "NO_STOCK"}), 200
    try:
        stock = max(0, int(stock))
    except Exception:
        return jsonify({"id": idml, "result": "BAD_STOCK"}), 200

    # 6) Armar payload y PUT (o emular)
    payload = _build_put_payload(stock)

    if emulate:
        # Emulación de 2s y "200"
        time.sleep(2)
        return jsonify({"id": idml, "result": 200}), 200

    # PUT real
    try:
        url = f"https://api.mercadolibre.com/items/{idml}"
        headers = {"Content-Type": "application/json", **_prefer_token_header()}
        r = requests.put(url, headers=headers, json=payload, timeout=20)
        return jsonify({"id": idml, "result": r.status_code}), 200
    except Exception:
        # Error de red / timeout
        return jsonify({"id": idml, "result": 0}), 200


# -------------------- (opc) Chequeo múltiple GET, si lo querés usar) --------------------
@_bp().route('/api/items/check', methods=['POST'], endpoint='check_items')
def check_items():
    """
    Body: { "ids": ["MLA1","MLA2"] }
    Resp: { "results": { "MLA1": {"code":200,"data":{...}}, "MLA2": {"code":404} } }
    """
    data = request.get_json(silent=True) or {}
    ids = [str(x).strip() for x in (data.get('ids') or []) if str(x).strip()]
    if not ids:
        return jsonify({"error": "ids_required"}), 400

    # Verificar token primero (coherente con bulk_put)
    ok_token, token_info, token_status = _check_token_valid()
    if not ok_token:
        return jsonify(token_info or {"error": "token_invalid"}), (token_status or 401)

    out = {}
    for idml in ids:
        js, code = _ml_get_item_backoff(idml)
        if code == 200:
            shipping = (js or {}).get('shipping') or {}
            out[idml] = {
                "code": 200,
                "data": {
                    "status": js.get("status"),
                    "shipping_logistic_type": shipping.get("logistic_type"),
                    "available_quantity": js.get("available_quantity"),
                }
            }
        else:
            out[idml] = {"code": code, "data": None}

    return jsonify({"results": out}), 200
