# app/controllers/purchases/invoices_suppliers_detail.py
from flask import Blueprint, render_template, request, redirect, jsonify, current_app
from app.integrations.apimongo.get_title import get_title, get_title_raw
from app.db import get_conn
from app.utils.order_status import estado_logico

import time
import requests
from app.integrations.rayo.rayo_token import _cfg as rayo_cfg  # usamos URL_RAYO y APIRAYO

# Blueprint
invoices_detail_bp = Blueprint(
    'invoices_suppliers_detail',  # esto es lo que usás en url_for: 'invoices_suppliers_detail.*'
    __name__,
    url_prefix='/purchases/invoices_suppliers/detail'
)


@invoices_detail_bp.route('/titulo/<isbn>')
def titulo_por_isbn(isbn):
    title = get_title(isbn)
    return jsonify({"isbn": isbn, "title": title})

# (opcional, para debug rápido desde el navegador)
@invoices_detail_bp.route('/titulo_raw/<isbn>')
def titulo_raw(isbn):
    data = get_title_raw(isbn)
    return jsonify(data or {"isbn": isbn, "title": None})

# === Vista principal de detalle de factura ===
@invoices_detail_bp.route('/<nro_fc>')
def view(nro_fc):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            isup.id,
            isup.fecha,
            isup.proveedor,
            isup.isbn,
            isup.importe,
            isup.order_id,
            isup.tipo_factura,
            isup.tc,
            CASE WHEN ira.sku IS NULL THEN 0 ELSE 1 END AS en_rayo
        FROM invoices_suppliers isup
        LEFT JOIN inventario_rayo_ava ira
            ON isup.isbn REGEXP '^[0-9]+$' AND ira.sku = CAST(isup.isbn AS UNSIGNED)
        WHERE isup.nro_fc = %s
    """, (nro_fc,))
    items = cursor.fetchall()
    tc = items[0][7] if items else None
    cursor.close()
    return render_template('purchases/invoices_suppliers_detail.html', nro_fc=nro_fc, items=items, tc=tc)

# === Buscar órdenes por ISBN (para el modal "Vincular orden") ===
@invoices_detail_bp.route('/buscar_ordenes_por_isbn', methods=['POST'])
def buscar_ordenes_por_isbn():
    isbn = request.json.get('isbn')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            o.order_id,
            o.created_at,
            o.total_amount,
            o.status,
            s.status AS shipment_status,
            s.substatus,
            oi.id AS order_item_id,
            oi.quantity,
            COALESCE(COUNT(isup.id), 0) AS unidades_vinculadas
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        LEFT JOIN invoices_suppliers isup 
            ON isup.order_id = o.order_id AND isup.isbn = oi.seller_sku
        WHERE oi.seller_sku = %s
        GROUP BY o.order_id, oi.id
        ORDER BY o.created_at DESC
    """, (isbn,))
    rows = cursor.fetchall()
    cursor.close()

    ordenes = []
    for row in rows:
        estado = estado_logico(row[3], row[4], row[5])
        ordenes.append({
            "order_id": row[0],
            "fecha": row[1].strftime('%d-%m-%Y') if row[1] else None,
            "total": row[2],
            "estado": estado,
            "order_item_id": row[6],
            "quantity": row[7],
            "vinculadas": row[8],
        })

    return jsonify(ordenes)

# === Vincular / Desvincular orden ===
@invoices_detail_bp.route('/vincular_orden', methods=['POST'])
def vincular_orden():
    item_id = request.form.get('item_id')
    order_id = request.form.get('order_id')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET order_id = %s
        WHERE id = %s
    """, (order_id, item_id))
    conn.commit()
    cursor.close()
    return redirect(request.referrer)

@invoices_detail_bp.route('/desvincular_orden', methods=['POST'])
def desvincular_orden():
    item_id = request.form.get('item_id')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET order_id = NULL
        WHERE id = %s
    """, (item_id,))
    conn.commit()
    cursor.close()
    return redirect(request.referrer)

# === Actualizar tipo de cambio de la factura ===
@invoices_detail_bp.route('/actualizar_tc_factura', methods=['POST'])
def actualizar_tc_factura():
    nro_fc = request.form.get('nro_fc')
    tc = request.form.get('tc')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET tc = %s
        WHERE nro_fc = %s
    """, (tc, nro_fc))
    conn.commit()
    cursor.close()
    return redirect(request.referrer)

# === Faltantes en Rayo (para el modal "Crear en Rayo") ===
@invoices_detail_bp.route('/faltantes/<nro_fc>')
def faltantes_en_rayo(nro_fc):
    """
    Devuelve los productos de la factura que NO están en inventario_rayo_ava,
    agrupados por SKU/ISBN (normalizado y raw), con repeticiones e importe total.
    Requiere MySQL 8+ por REGEXP_REPLACE.
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            TRIM(isup.isbn)                                                   AS isbn_raw,
            REGEXP_REPLACE(TRIM(isup.isbn), '[^0-9]', '')                     AS sku_norm,
            COUNT(*)                                                          AS repeticiones,
            COALESCE(SUM(isup.importe), 0)                                    AS importe_total,
            MIN(isup.fecha)                                                   AS fecha_min,
            MAX(isup.fecha)                                                   AS fecha_max,
            GROUP_CONCAT(DISTINCT isup.proveedor ORDER BY isup.proveedor
                         SEPARATOR ', ')                                      AS proveedores
        FROM invoices_suppliers isup
        LEFT JOIN inventario_rayo_ava ira
          ON TRIM(isup.isbn) REGEXP '^[0-9]+$'
         AND ira.sku = CAST(TRIM(isup.isbn) AS UNSIGNED)
        WHERE isup.nro_fc = %s
          AND ira.sku IS NULL
        GROUP BY TRIM(isup.isbn), REGEXP_REPLACE(TRIM(isup.isbn), '[^0-9]', '')
        ORDER BY fecha_max DESC
    """, (nro_fc,))
    rows = cursor.fetchall()
    cursor.close()

    items = []
    for r in rows:
        isbn_raw, sku_norm, repeticiones, imp_total, fmin, fmax, proveedores = r
        items.append({
            "isbn": isbn_raw,
            "sku_norm": sku_norm,
            "repeticiones": int(repeticiones or 0),
            "importe_total": float(imp_total or 0),
            "fecha_min": fmin.strftime('%d-%m-%Y') if fmin else None,
            "fecha_max": fmax.strftime('%d-%m-%Y') if fmax else None,
            "proveedores": proveedores or "",
            "apto_inventario": 1 if (sku_norm and sku_norm.isdigit()) else 0
        })

    return jsonify({"nro_fc": nro_fc, "total": len(items), "items": items})


# === Helpers Rayo (Auth + Bearer) ===
RAYO_TIMEOUT = 20  # segundos

def _extract_token_recursive(obj):
    """Busca token en claves comunes y en anidados típicos (AuthWithAPIkey, data, etc.)."""
    if not isinstance(obj, dict):
        return None
    for k in ("access_token", "token", "accessToken", "accesToken"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for subkey in ("data", "AuthWithAPIkey", "AuthWithApiKey", "auth", "result"):
        sub = obj.get(subkey)
        if isinstance(sub, dict):
            t = _extract_token_recursive(sub)
            if t:
                return t
    return None

def _rayo_auth_token():
    """
    Pide token a /auth con x-api-key y devuelve Bearer.
    """
    url_rayo, api_rayo = rayo_cfg()
    if not url_rayo or not api_rayo:
        return None, "Faltan env: URL_RAYO o APIRAYO"

    endpoint = url_rayo.rstrip("/") + "/auth"
    headers = {"x-api-key": api_rayo, "Accept": "application/json"}
    try:
        resp = requests.post(endpoint, headers=headers, timeout=RAYO_TIMEOUT)
        if not resp.ok:
            return None, f"Auth {resp.status_code}: {resp.text[:200]}"
        try:
            body = resp.json()
        except ValueError:
            body = {}
        token = _extract_token_recursive(body)
        if not token:
            return None, "No se pudo extraer access_token del auth"
        return token, None
    except requests.RequestException as e:
        return None, f"request_error: {e}"

def _rayo_post_productos(base_url: str, bearer: str, payload: dict):
    url = base_url.rstrip("/") + "/product/new"
    headers = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, timeout=RAYO_TIMEOUT)

def _rayo_get_producto(base_url: str, bearer: str, sku: str):
    url = base_url.rstrip("/") + f"/product/{sku}"
    headers = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
    return requests.get(url, headers=headers, timeout=RAYO_TIMEOUT)

def _extract_sku_from_get(json_obj):
    """
    Extrae SKU de respuestas típicas:
    - {"sku": "..."}
    - {"data": {"sku": "..."}}
    - {"producto": {"sku": "..."}}
    - {"producto": [{"sku": "..."}]}
    - {"data": {"producto": {"sku": "..."}}} / lista
    """
    if not isinstance(json_obj, dict):
        return None
    # nivel 0
    if isinstance(json_obj.get("sku"), (str, int)):
        return str(json_obj.get("sku"))
    # data.sku
    data = json_obj.get("data")
    if isinstance(data, dict) and isinstance(data.get("sku"), (str, int)):
        return str(data.get("sku"))
    # producto dict
    prod = json_obj.get("producto")
    if isinstance(prod, dict) and isinstance(prod.get("sku"), (str, int)):
        return str(prod.get("sku"))
    # producto lista
    if isinstance(prod, list) and prod:
        first = prod[0]
        if isinstance(first, dict) and isinstance(first.get("sku"), (str, int)):
            return str(first.get("sku"))
    # data.producto (dict o lista)
    if isinstance(data, dict):
        prod2 = data.get("producto")
        if isinstance(prod2, dict) and isinstance(prod2.get("sku"), (str, int)):
            return str(prod2.get("sku"))
        if isinstance(prod2, list) and prod2:
            first2 = prod2[0]
            if isinstance(first2, dict) and isinstance(first2.get("sku"), (str, int)):
                return str(first2.get("sku"))
    return None


# === Crear en Rayo (POST + verificación real por GET) ===
@invoices_detail_bp.route('/<nro_fc>/rayo/create', methods=['POST'])
def rayo_create_items(nro_fc):
    """
    Recibe:
    {
      "nro_fc": "60791",
      "items": [{"sku":"...", "titulo":"...", "foto":"..."}]
    }

    Versión actual:
    - Auth con /auth (x-api-key) y uso de Bearer para /product/*
    - Payload FORZADO de prueba (comentarios para dinámicos)
        nombre     = "ITEM DE PRUEBA"    # it["titulo"]
        imagen_url = "https://sys.apricor.com.mx/images/np.jpg"  # it["foto"]
        sku        = "TESTAPI02"         # it["sku"]
        upc        = "TESTAPI02"         # it["sku"]
        dimensiones = todas "5"
    - GET /product/TESTAPI02: ok=True sólo si confirma el SKU
    """
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []

    errors = []
    clean_items = []

    for idx, it in enumerate(items):
        sku = (it.get("sku") or "").strip()
        titulo = (it.get("titulo") or "").strip()
        foto = (it.get("foto") or "").strip()
        if not sku or not titulo:
            errors.append({"index": idx, "sku": sku, "error": "SKU y título son obligatorios"})
            continue
        clean_items.append({"sku": sku, "titulo": titulo, "foto": foto})

    if not clean_items:
        return jsonify({
            "ok": False,
            "nro_fc": nro_fc,
            "received": len(items),
            "valid": 0,
            "invalid": len(errors),
            "errors": errors,
            "message": "No hay items válidos para enviar a Rayo"
        }), 400

    # === Config Rayo ===
    url_rayo, _ = rayo_cfg()
    bearer, auth_err = _rayo_auth_token()
    if not bearer:
        current_app.logger.warning(f"[RAYO] Auth error: {auth_err}")
        return jsonify({
            "ok": False,
            "nro_fc": nro_fc,
            "error": f"Auth error: {auth_err}"
        }), 502

    # --- Payload DINÁMICO (con fallback de imagen) ---
    PLACEHOLDER_IMG = "https://sys.apricor.com.mx/images/np.jpg"

    productos = []
    for it in clean_items:
        sku = (it.get("sku") or "").strip()
        titulo = (it.get("titulo") or "").strip()

        # fallback de imagen si viene vacía, nula o sin http/https
        foto = (it.get("foto") or "").strip()
        if not foto or not foto.lower().startswith(("http://", "https://")):
            foto = PLACEHOLDER_IMG

        productos.append({
            "nombre": titulo,
            "imagen_url": foto,
            "sku": sku,
            "upc": sku,
            "dimension": {
                "data": {
                    "altura": "5",
                    "ancho": "5",
                    "largo": "5",
                    "peso": "5",
                    "volumen": "5"
                }
            }
        })

    payload = {"productos": productos}

    # --- POST /product/new (Bearer) ---
    try:
        post_resp = _rayo_post_productos(url_rayo, bearer, payload)
        post_status = post_resp.status_code
        try:
            post_body = post_resp.json()
        except Exception:
            post_body = {"raw": post_resp.text}
    except requests.RequestException as e:
        return jsonify({
            "ok": False,
            "nro_fc": nro_fc,
            "error": "Fallo POST a Rayo",
            "detail": str(e),
            "payload": payload
        }), 502

    if post_status >= 400 and post_status != 409:
        current_app.logger.warning(f"[RAYO] POST /product/new fallo: {post_status} body={str(post_body)[:300]}")
        return jsonify({
            "ok": False,
            "nro_fc": nro_fc,
            "post": {"status": post_status, "response": post_body},
            "message": "Rayo no aceptó la creación"
        }), 502

    # Breve espera por consistencia eventual
    time.sleep(1.0)

    # --- GET /product/{sku} para constatar (por cada item real) ---
    verificaciones = []
    verified_all = True

    for it in clean_items:
        sku_para_get = (it.get("sku") or "").strip()
        try:
            g = _rayo_get_producto(url_rayo, bearer, sku_para_get)
            status = g.status_code
            try:
                body = g.json()
            except Exception:
                body = {"raw": g.text}

            sku_detectado = _extract_sku_from_get(body)
            ok_item = (status == 200 and sku_detectado and str(sku_detectado).strip() == sku_para_get)

            verificaciones.append({
                "sku": sku_para_get,
                "get_status": status,
                "ok": ok_item,
                "data": body
            })

            if not ok_item:
                verified_all = False

        except requests.RequestException as e:
            verificaciones.append({
                "sku": sku_para_get,
                "get_status": None,
                "ok": False,
                "error": str(e)
            })
            verified_all = False

    current_app.logger.info(f"[RAYO] POST status={post_status} verified_all={verified_all}")

    # --- DB: upsert en inventario_rayo_ava por cada SKU verificado OK ---
    # (usamos título/foto del request como fallback si el GET no los trae)
    clean_by_sku = { (it.get("sku") or "").strip(): it for it in clean_items }

    db_results = []
    conn = get_conn()
    cur = conn.cursor()
    try:
        for v in verificaciones:
            sku_req = (v.get("sku") or "").strip()
            if not v.get("ok"):
                db_results.append({"sku": sku_req, "upsert": False, "reason": "no_verified"})
                continue

            # Extraer el producto del body (acepta dict o lista, con/sin "data")
            prod = None
            body = v.get("data") or {}
            if isinstance(body, dict):
                prod = body.get("producto")
                if isinstance(prod, list) and prod:
                    prod = prod[0]
                elif not isinstance(prod, dict):
                    data_node = body.get("data")
                    if isinstance(data_node, dict):
                        prod = data_node.get("producto")
                        if isinstance(prod, list) and prod:
                            prod = prod[0]

            if not isinstance(prod, dict):
                db_results.append({"sku": sku_req, "upsert": False, "reason": "no_producto_in_body"})
                continue

            # sku numérico (tabla usa BIGINT UNSIGNED)
            sku_str = str(prod.get("sku") or sku_req or "").strip()
            try:
                sku_num = int(sku_str)
            except Exception:
                db_results.append({"sku": sku_req, "upsert": False, "reason": "sku_not_numeric"})
                continue

            # mapear con fallbacks
            titulo_req = (clean_by_sku.get(sku_req, {}).get("titulo") or "").strip()
            foto_req   = (clean_by_sku.get(sku_req, {}).get("foto") or "").strip()

            nombre = (prod.get("nombre") or titulo_req or "SIN NOMBRE").strip()
            imagen = (prod.get("imagen_url") or foto_req or "").strip()
            if not imagen.lower().startswith(("http://", "https://")):
                imagen = PLACEHOLDER_IMG
            upc = (str(prod.get("upc")) if prod.get("upc") else sku_str)

            # UPSERT: solo afectamos nombre/imagen/upc (stocks/almacén quedan igual)
            sql = """
                INSERT INTO inventario_rayo_ava (sku, nombre, imagen, upc)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    nombre = VALUES(nombre),
                    imagen = VALUES(imagen),
                    upc    = VALUES(upc)
            """
            try:
                # opcional: reconectar si la conexión se durmió
                try:
                    conn.ping(True)
                except Exception:
                    pass

                cur.execute(sql, [sku_num, nombre, imagen, upc])
                conn.commit()
                db_results.append({"sku": sku_str, "upsert": True, "rowcount": cur.rowcount})
            except Exception as e:
                conn.rollback()
                db_results.append({"sku": sku_str, "upsert": False, "error": str(e)})
    finally:
        cur.close()
        # NO cerrar conn aquí; lo cierra flask_mysqldb en teardown


    ok_final = verified_all and all(r.get("upsert") for r in db_results)

    return jsonify({
        "ok": ok_final,
        "nro_fc": nro_fc,
        "received": len(items),
        "valid": len(clean_items),
        "invalid": len(errors),
        "errors": errors,
        "post": {"status": post_status, "response": post_body},
        "verify": verificaciones,
        "db": db_results,
        "message": ("Creados/verificados y guardados en DB" if ok_final
                    else "Verificá 'verify' y 'db' para ver cuáles fallaron")
    }), (200 if ok_final else 502)
