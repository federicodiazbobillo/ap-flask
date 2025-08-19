# app/controllers/items/mercadolibre/sync_celesa/api_ops.py
import time
import requests
from flask import request, jsonify

# Blueprint helper (no exponer global)
def _bp():
    from .index import sync_celesa_bp
    return sync_celesa_bp

# DB
from app.db import get_conn

# Reglas de sale_terms
from .parametros_sale_terms_celesa import get_sale_term_for_stock

# Token (opcional)
try:
    # verificar_meli() -> (access_token, user_id, error)
    from app.integrations.mercadolibre.services.token_service import verificar_meli
except Exception:
    verificar_meli = None


# -------------------- Helpers HTTP ML --------------------
def _prefer_token_header():
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

def _ml_get_item(idml, timeout=15):
    url = f"https://api.mercadolibre.com/items/{idml}"
    headers = _prefer_token_header()
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code in (401, 403) and headers:
            # reintento sin token por si aplica (sólo GET)
            r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json(), 200
        return None, r.status_code
    except Exception:
        return None, 0  # error de red/timeout

def _ml_get_item_backoff(idml, max_retries=5):
    tries = 0
    while True:
        js, code = _ml_get_item(idml)
        if code in (429, 500, 502, 503) and tries < max_retries:
            time.sleep(1.0)
            tries += 1
            continue
        return js, code

def _safe_json_text(resp):
    try:
        return resp.json()
    except Exception:
        try:
            return resp.text
        except Exception:
            return None

def _ml_put_item(idml, payload, timeout=25):
    """Devuelve (status_code, detail) donde detail es json o texto de ML (si hay)."""
    url = f"https://api.mercadolibre.com/items/{idml}"
    headers = {"Content-Type": "application/json", **_prefer_token_header()}
    try:
        r = requests.put(url, headers=headers, json=payload, timeout=timeout)
        detail = _safe_json_text(r)
        # Para PUT, sin token no sirve, pero si tu app tuviese permisos anónimos (raro) podrías reintentar:
        if r.status_code in (401, 403) and "Authorization" in headers:
            r2 = requests.put(url, headers={"Content-Type": "application/json"}, json=payload, timeout=timeout)
            return r2.status_code, _safe_json_text(r2)
        return r.status_code, detail
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# -------------------- Helpers de negocio --------------------
def _get_stock_celesa(idml: str) -> int:
    """Lee stock_celesa desde items_meli. Si falta, 0."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT stock_celesa FROM items_meli WHERE idml=%s", (idml,))
        row = cur.fetchone()
        if not row or row[0] is None:
            return 0
        try:
            return int(row[0])
        except Exception:
            return 0
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

def _is_full_item(js: dict) -> bool:
    """Detecta si la publicación es FULL."""
    shipping = (js or {}).get("shipping") or {}
    logistic = (shipping.get("logistic_type") or "").lower()
    if logistic == "fulfillment":
        return True
    # fallback: algunos payloads incluyen tag "fulfillment"
    tags = js.get("tags") or []
    return any((str(t).lower() == "fulfillment") for t in tags)

def _build_sale_terms_for(stock: int) -> list:
    """Arma sale_terms según reglas y stock."""
    if stock <= 0:
        manuf_days = 35  # explícito para stock 0
    else:
        rule = get_sale_term_for_stock(stock, provider='celesa') or {}
        try:
            manuf_days = int(rule.get("delivery_days") or 15)
        except Exception:
            manuf_days = 15
    return [
        {"id": "MANUFACTURING_TIME", "value_name": f"{manuf_days} días"},
        {"id": "WARRANTY_TIME", "value_name": "90 días"},
        {"id": "WARRANTY_TYPE", "value_id": "2230279"},
    ]

def _build_put_payload(stock: int) -> dict:
    """Payload final para PUT."""
    status = "active" if stock > 0 else "paused"
    return {
        "available_quantity": int(stock),
        "status": status,
        "sale_terms": _build_sale_terms_for(stock),
    }


# -------------------- API: PUT por publicación (con GET y validaciones) --------------------
@_bp().route('/bulk-put', methods=['POST'], endpoint='bulk_put')
def bulk_put():
    """
    Body esperado:
      { "ids": ["MLA123456"] }   # el front manda 1 por request

    Flujo por idml:
      1) GET /items/{idml}    -> si != 200 => "GET:{code}"
      2) Si FULL              -> "full"
      3) Si status !in {active,paused} -> "<status>"
      4) payload (stock + sale_terms) desde DB y reglas
      5) sleep(2) y PUT       -> devolver código del PUT
    """
    data = request.get_json(silent=True) or {}
    ids = [str(x).strip() for x in (data.get('ids') or []) if str(x).strip()]
    if not ids:
        return jsonify({"error": "ids_required"}), 400

    results = {}
    debug = {}

    for idml in ids:
        try:
            # 1) GET
            item_js, get_code = _ml_get_item_backoff(idml)
            if get_code != 200:
                results[idml] = f"GET:{get_code}"
                debug[idml] = {"step": "GET", "code": get_code}
                continue

            # 2) FULL?
            if _is_full_item(item_js or {}):
                results[idml] = "full"
                debug[idml] = {"step": "SKIP", "reason": "full"}
                continue

            # 3) status permitido?
            curr_status = (item_js or {}).get("status") or ""
            if curr_status not in ("active", "paused"):
                results[idml] = str(curr_status or "unknown_status")
                debug[idml] = {"step": "SKIP", "reason": "status_not_updatable", "status": curr_status}
                continue

            # 4) stock + sale_terms
            stock = _get_stock_celesa(idml)
            payload = _build_put_payload(stock)

            # 5) PUT (con sleep para que el slider se vea)
            time.sleep(2)
            put_code, put_detail = _ml_put_item(idml, payload)
            results[idml] = put_code
            debug[idml] = {"step": "PUT", "code": put_code, "payload": payload, "detail": put_detail}

        except Exception as e:
            # pase lo que pase, no rompemos todo el endpoint
            results[idml] = "ERR"
            debug[idml] = {"step": "EXC", "error": f"{type(e).__name__}: {e}"}

    # results es lo que usa tu UI; debug te ayuda a ver el motivo real si no es 200
    return jsonify({"results": results, "debug": debug}), 200
