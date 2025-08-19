# condiciones_generales.py — Listado, token, normalización/verificación, workers
import math
import re
import time
import uuid
import threading
import requests




from flask import (
    render_template, request, redirect, url_for, jsonify, current_app
)


# OJO: no exponemos el blueprint como variable global en este módulo.
# Usamos un helper para obtenerlo cuando hace falta:
def _bp():
    from .index import sync_celesa_bp
    return sync_celesa_bp

from .index import (
    PAGE_SIZE, BATCH_SIZE_DEFAULT, NULL_SENTINEL,
    ISBN_MIN, ISBN_MAX, JOBS, build_where_for_list
)
from app.db import get_conn

# Token (opcional)
try:
    # Firma del sistema: verificar_meli() -> (access_token, user_id, error)
    from app.integrations.mercadolibre.services.token_service import verificar_meli
except Exception:
    verificar_meli = None

# ------------------- Helper: threads con app_context -------------------
def _thread_entry(app, target, *args, **kwargs):
    with app.app_context():
        target(*args, **kwargs)


def _start_thread(target, *args, **kwargs):
    app = current_app._get_current_object()
    t = threading.Thread(
        target=_thread_entry,
        args=(app, target, *args),
        kwargs=kwargs,
        daemon=True,
    )
    t.start()
    return t


# ------------------- Utilidades comunes -------------------
def _is_isbn13_int(val):
    return isinstance(val, int) and ISBN_MIN <= val <= ISBN_MAX


def _digits(s):
    return re.sub(r"\D+", "", s or "")


def _extract_gtin_from_item_json(js):
    """
    Busca GTIN/ISBN dentro de attributes. Devuelve un int de 13 dígitos o None.
    """
    attrs = (js or {}).get("attributes") or []
    for a in attrs:
        aid = (a.get("id") or "").strip().upper()
        aname = (a.get("name") or "").strip().upper()
        if aid == "GTIN" or "ISBN" in aname:
            candidates = []
            if a.get("value_name"):
                candidates.append(a["value_name"])
            for v in (a.get("values") or []):
                if v and v.get("name"):
                    candidates.append(v["name"])
            for c in candidates:
                d = _digits(str(c))
                if len(d) == 13 and d.isdigit():
                    try:
                        num = int(d)
                        if _is_isbn13_int(num):
                            return num
                    except Exception:
                        pass
    return None


def _prefer_token_header():
    """
    Usa la firma del sistema:
      access_token, user_id, error = verificar_meli()
    y devuelve Authorization si corresponde.
    """
    if not verificar_meli:
        return {}
    try:
        access_token, user_id, error = verificar_meli()
        if error or not access_token:
            return {}
        return {"Authorization": f"Bearer {access_token}"}
    except Exception:
        return {}


def _get_ml_item_raw(idml):
    """
    Devuelve (json_or_none, http_status_code). Intenta CON token primero.
    """
    base = f"https://api.mercadolibre.com/items/{idml}"
    headers = _prefer_token_header()
    try:
        r = requests.get(base, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json(), 200
        # Si 401/403 con token, probamos sin headers
        if r.status_code in (401, 403) and headers:
            try:
                r2 = requests.get(base, timeout=15)
                if r2.status_code == 200:
                    return r2.json(), 200
                return None, r2.status_code
            except Exception:
                return None, 0
        return None, r.status_code
    except Exception:
        return None, 0  # 0 = error de red/timeout


def _get_ml_item_raw_backoff(idml, max_retries=5):
    """Backoff simple para 429/500/502/503."""
    attempt = 0
    while True:
        js, code = _get_ml_item_raw(idml)
        if code in (429, 500, 503, 502):
            if attempt >= max_retries:
                return js, code
            time.sleep(1.0)
            attempt += 1
            continue
        return js, code


# ------------------- Parseo de filtros para ASYNC/FORM -------------------
def _parse_filters_from_request():
    """
    Acepta JSON o form-data:
      {
        "selected_statuses": ["__NULL__", "active", ...],
        "isbn_ok": null | "valid" | "invalid",
        "batch_size": 100,
        "process_all": false,
        "max_items": 5000
      }
    """
    payload = request.get_json(silent=True)
    if payload and isinstance(payload, dict):
        selected_statuses = payload.get("selected_statuses") or []
        if isinstance(selected_statuses, str):
            selected_statuses = [s.strip() for s in selected_statuses.split(",") if s.strip()]
        isbn_ok = payload.get("isbn_ok") or None
        try:
            batch_size = int(payload.get("batch_size", BATCH_SIZE_DEFAULT))
            if batch_size < 1 or batch_size > 1000:
                batch_size = BATCH_SIZE_DEFAULT
        except Exception:
            batch_size = BATCH_SIZE_DEFAULT
        process_all = bool(payload.get("process_all", False))
        try:
            max_items = int(payload.get("max_items", 5000))
        except Exception:
            max_items = 5000
    else:
        selected_statuses = request.form.getlist('status')
        if len(selected_statuses) == 1 and ',' in selected_statuses[0]:
            selected_statuses = [s.strip() for s in selected_statuses[0].split(',') if s.strip()]
        isbn_ok = request.form.get('isbn_ok') or None
        try:
            batch_size = int(request.form.get('batch_size', BATCH_SIZE_DEFAULT))
            if batch_size < 1 or batch_size > 1000:
                batch_size = BATCH_SIZE_DEFAULT
        except Exception:
            batch_size = BATCH_SIZE_DEFAULT
        process_all = request.form.get('process_all') == '1'
        try:
            max_items = int(request.form.get('max_items', 5000))
        except Exception:
            max_items = 5000

    include_null = (NULL_SENTINEL in selected_statuses)
    statuses_only = [s for s in selected_statuses if s and s != NULL_SENTINEL]

    return {
        "selected_statuses": selected_statuses,
        "isbn_ok": isbn_ok,
        "include_null": include_null,
        "statuses_only": statuses_only,
        "batch_size": batch_size,
        "process_all": process_all,
        "max_items": max_items,
    }


def _count_where(conn, table, where_sql, params):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_sql}", params)
    n = cur.fetchone()[0] or 0
    cur.close()
    return n


def _job_make(job_type, filters):
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "type": job_type,          # "normalize" | "verify"
        "state": "pending",        # pending|running|done|error
        "filters": filters,
        "total": 0,
        "processed": 0,
        "ok": 0,                   # normalize: norm_ok; verify: vs_ok
        "code": 0,                 # normalize: norm_bad; verify: vs_code
        "last_idml": None,
        "last_code": None,
        "unexpected": False,
        "unexpected_code": None,
        "unexpected_idml": None,
        "started_at": None,
        "finished_at": None,
        "message": "",
    }
    JOBS[job_id] = job
    return job


# ------------------- UI: listado / página principal -------------------
@_bp().route('/sync_celesa')
def sync_celesa_list():
    # Paginación
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    if page < 1:
        page = 1

    # Tab activa
    active_tab = request.args.get('tab', 'general')

    # Filtros de status
    selected_statuses = request.args.getlist('status')
    if len(selected_statuses) == 1 and ',' in selected_statuses[0]:
        selected_statuses = [s.strip() for s in selected_statuses[0].split(',') if s.strip()]

    include_null = False
    statuses_only = []
    for s in selected_statuses:
        if s == NULL_SENTINEL:
            include_null = True
        elif s != "":
            statuses_only.append(s)

    # Filtro ISBN
    isbn_ok = request.args.get('isbn_ok')
    analyze_flag = (request.args.get('analyze') == '1')

    # Filtro de stock (para la pestaña de stock)
    stock_filter = request.args.get('stock_filter')  # p.ej. 'celesa_zero_ml_positive'

    conn = get_conn()
    cur = conn.cursor()

    # Status disponibles
    cur.execute("SELECT DISTINCT status FROM items_meli ORDER BY status IS NULL, status")
    available_statuses = [row[0] for row in cur.fetchall()]

    # WHERE usando helper centralizado
    where_sql, params = build_where_for_list(statuses_only, include_null, isbn_ok, stock_filter)

    # Total
    cur.execute(f"SELECT COUNT(*) FROM items_meli WHERE {where_sql}", params)
    total = cur.fetchone()[0] or 0

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * PAGE_SIZE

    # Datos
    data_sql = f"""
        SELECT idml, isbn, status, stock_idml, stock_celesa
        FROM items_meli
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """
    data_params = params + [PAGE_SIZE, offset]
    cur.execute(data_sql, data_params)
    rows = cur.fetchall()

    # Análisis ISBN (opcional)
    isbn_ok_count = None
    isbn_bad_count = None
    if analyze_flag:
        cur.execute(f"""
            SELECT
              SUM(CASE WHEN (isbn BETWEEN %s AND %s) THEN 1 ELSE 0 END) AS ok_count,
              SUM(CASE WHEN (isbn IS NULL OR isbn < %s OR isbn > %s) THEN 1 ELSE 0 END) AS bad_count
            FROM items_meli
            WHERE {where_sql}
        """, [ISBN_MIN, ISBN_MAX, ISBN_MIN, ISBN_MAX, *params])
        rowc = cur.fetchone()
        if rowc:
            isbn_ok_count, isbn_bad_count = rowc[0] or 0, rowc[1] or 0

    cur.close()

    start = (offset + 1) if total > 0 else 0
    end = min(offset + PAGE_SIZE, total)

    return render_template(
        'items/mercadolibre/sync_celesa/index.html',
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
        page_size=PAGE_SIZE,
        start=start,
        end=end,
        available_statuses=available_statuses,
        selected_statuses=selected_statuses,
        NULL_SENTINEL=NULL_SENTINEL,
        isbn_ok=isbn_ok,
        analyze=analyze_flag,
        isbn_ok_count=isbn_ok_count,
        isbn_bad_count=isbn_bad_count,
        active_tab=active_tab,
        stock_filter=stock_filter,
        # banners sincrónicos (compat: apagados aquí)
        normalized=False, norm_total=None, norm_ok=None, norm_bad=None,
        verified=False, vs_total=None, vs_ok=None, vs_code=None,
        unexpected=False, unexpected_code=None, unexpected_idml=None
    )


# ---------- Alias legacy: /items_meli -> /sync_celesa (GET)
@_bp().route('/items_meli')
def items_meli_legacy():
    params = request.args.to_dict(flat=False)  # preserva repetidos
    return redirect(url_for('sync_celesa_bp.index', **params), code=302)


# ------------------- Endpoints SINCRÓNICOS (compat) -------------------


@_bp().route('/sync_celesa/normalize', methods=['POST'])
@_bp().route('/items_meli/normalize_isbn', methods=['POST'])  # alias legacy
def normalize_isbn():
    """
    Compat sincrónica. Recomendado usar /sync_celesa/normalize_start + polling.
    """
    selected_statuses = request.form.getlist('status')
    if len(selected_statuses) == 1 and ',' in selected_statuses[0]:
        selected_statuses = [s.strip() for s in selected_statuses[0].split(',') if s.strip()]
    isbn_ok = request.form.get('isbn_ok') or None

    include_null = False
    statuses_only = []
    for s in selected_statuses:
        if s == NULL_SENTINEL:
            include_null = True
        elif s != "":
            statuses_only.append(s)

    try:
        batch_size = int(request.form.get('batch_size', BATCH_SIZE_DEFAULT))
        if batch_size < 1 or batch_size > 1000:
            batch_size = BATCH_SIZE_DEFAULT
    except Exception:
        batch_size = BATCH_SIZE_DEFAULT

    process_all = request.form.get('process_all') == '1'
    try:
        max_items = int(request.form.get('max_items', 5000))
    except Exception:
        max_items = 5000

    conn = get_conn()
    cur = conn.cursor()

    base_where = [
        "(isbn IS NULL OR isbn < %s OR isbn > %s)",
        "(isbn IS NULL OR isbn <> 111)",
    ]
    base_params = [ISBN_MIN, ISBN_MAX]

    if statuses_only:
        placeholders = ",".join(["%s"] * len(statuses_only))
        base_where.append(f"status IN ({placeholders})")
        base_params.extend(statuses_only)

    if include_null:
        base_where.append("(status IS NULL OR status = '')")

    if isbn_ok == 'valid':
        base_where.append("(isbn BETWEEN %s AND %s)")
        base_params.extend([ISBN_MIN, ISBN_MAX])

    where_sql = " AND ".join(base_where)

    norm_total = 0
    norm_ok = 0
    norm_bad = 0

    while True:
        cur.execute(f"""
            SELECT idml
            FROM items_meli
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT %s
        """, base_params + [batch_size])
        ids = [row[0] for row in cur.fetchall() if row and row[0]]

        if not ids:
            break

        for idml in ids:
            js, code = _get_ml_item_raw_backoff(idml, max_retries=5)

            if code == 200:
                got = _extract_gtin_from_item_json(js or {})
                if got is not None:
                    new_isbn = int(got)
                    norm_ok += 1
                else:
                    new_isbn = 111
                    norm_bad += 1
            elif code in (404, 401, 403, 0, 429, 500, 503, 502):
                new_isbn = 111
                norm_bad += 1
            else:
                conn.commit()
                cur.close()
                return redirect(url_for(
                    'sync_celesa_bp.index',
                    page=1, status=selected_statuses, isbn_ok=isbn_ok,
                    unexpected=1, unexpected_code=code, unexpected_idml=idml
                ))

            try:
                cur.execute("""
                    UPDATE items_meli
                    SET isbn = %s, last_update_idml_catalog = NOW()
                    WHERE idml = %s
                """, (new_isbn, idml))
            except Exception:
                norm_bad += 1

        conn.commit()
        norm_total += len(ids)
        if not process_all or norm_total >= max_items:
            break

    cur.close()

    return redirect(url_for(
        'sync_celesa_bp.index',
        page=1, status=selected_statuses, isbn_ok=isbn_ok,
        normalized=1, norm_total=norm_total, norm_ok=0, norm_bad=norm_bad
    ))


@_bp().route('/sync_celesa/verify', methods=['POST'])
@_bp().route('/items_meli/verify', methods=['POST'])  # alias legacy
def verify_status():
    """
    Compat sincrónica. Recomendado usar /sync_celesa/verify_start + polling.
    """
    selected_statuses = request.form.getlist('status')
    if len(selected_statuses) == 1 and ',' in selected_statuses[0]:
        selected_statuses = [s.strip() for s in selected_statuses[0].split(',') if s.strip()]
    isbn_ok = request.form.get('isbn_ok') or None

    include_null = False
    statuses_only = []
    for s in selected_statuses:
        if s == NULL_SENTINEL:
            include_null = True
        elif s != "":
            statuses_only.append(s)

    try:
        batch_size = int(request.form.get('batch_size', BATCH_SIZE_DEFAULT))
        if batch_size < 1 or batch_size > 1000:
            batch_size = BATCH_SIZE_DEFAULT
    except Exception:
        batch_size = BATCH_SIZE_DEFAULT

    conn = get_conn()
    cur = conn.cursor()

    where_clauses = []
    params = []

    if statuses_only:
        placeholders = ",".join(["%s"] * len(statuses_only))
        where_clauses.append(f"status IN ({placeholders})")
        params.extend(statuses_only)

    if include_null:
        where_clauses.append("(status IS NULL OR status = '')")

    if isbn_ok == 'valid':
        where_clauses.append("(isbn BETWEEN %s AND %s)")
        params.extend([ISBN_MIN, ISBN_MAX])
    elif isbn_ok == 'invalid':
        where_clauses.append("(isbn IS NULL OR isbn < %s OR isbn > %s)")
        params.extend([ISBN_MIN, ISBN_MAX])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    cur.execute(f"""
        SELECT idml
        FROM items_meli
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT %s
    """, params + [batch_size])
    ids = [row[0] for row in cur.fetchall() if row and row[0]]

    vs_total = len(ids)
    vs_ok = 0
    vs_code = 0

    for idml in ids:
        js, code = _get_ml_item_raw_backoff(idml, max_retries=5)

        if code == 200:
            api_status = (js or {}).get("status")
            new_status = api_status if isinstance(api_status, str) and api_status else "200"
            if new_status == "200":
                vs_code += 1
            else:
                vs_ok += 1
        elif code == 404:
            new_status = "404"
            vs_code += 1
        elif code in (429, 500, 503, 502, 401, 403):
            new_status = str(code)
            vs_code += 1
        elif code == 0:
            new_status = "ERR"
            vs_code += 1
        else:
            conn.commit()
            cur.close()
            return redirect(url_for(
                'sync_celesa_bp.index',
                page=1, status=selected_statuses, isbn_ok=isbn_ok,
                unexpected=1, unexpected_code=code, unexpected_idml=idml
            ))

        try:
            cur.execute("""
                UPDATE items_meli
                SET status = %s
                WHERE idml = %s
            """, (new_status, idml))
        except Exception:
            vs_code += 1

    conn.commit()
    cur.close()

    return redirect(url_for(
        'sync_celesa_bp.index',
        page=1, status=selected_statuses, isbn_ok=isbn_ok,
        verified=1, vs_total=vs_total, vs_ok=vs_ok, vs_code=vs_code
    ))


# ------------------- Endpoints ASYNC -------------------
@_bp().route('/sync_celesa/normalize_start', methods=['POST'])
@_bp().route('/items_meli/normalize_start', methods=['POST'])  # alias legacy
def normalize_start():
    filters = _parse_filters_from_request()
    job = _job_make("normalize", filters)
    _start_thread(_run_job_normalize, job["id"])
    return jsonify({"job_id": job["id"]})


@_bp().route('/sync_celesa/verify_start', methods=['POST'])
@_bp().route('/items_meli/verify_start', methods=['POST'])  # alias legacy
def verify_start():
    filters = _parse_filters_from_request()
    job = _job_make("verify", filters)
    _start_thread(_run_job_verify, job["id"])
    return jsonify({"job_id": job["id"]})


@_bp().route('/sync_celesa/job_status/<job_id>')
@_bp().route('/items_meli/job_status/<job_id>')  # alias legacy
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "not_found"}), 404
    resp = {k: job.get(k) for k in (
        "id", "type", "state", "total", "processed", "ok", "code",
        "last_idml", "last_code", "unexpected", "unexpected_code",
        "unexpected_idml", "message", "started_at", "finished_at"
    )}
    resp["done"] = (job.get("state") == "done")
    return jsonify(resp)


# ------------------- /meli/token para el front -------------------
@_bp().route('/meli/token')
def meli_token():
    if not verificar_meli:
        return jsonify({"error": "token_service_not_available"}), 503
    try:
        access_token, user_id, error = verificar_meli()
        return jsonify({
            "access_token": access_token or None,
            "user_id": user_id,
            "error": error
        }), 200
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


# ------------------- Workers -------------------
def _run_job_normalize(job_id):
    job = JOBS.get(job_id)
    if not job:
        return
    job["state"] = "running"
    job["started_at"] = time.time()

    f = job["filters"]
    isbn_ok = f["isbn_ok"]
    include_null = f["include_null"]
    statuses_only = f["statuses_only"]
    batch_size = f["batch_size"]
    process_all = f["process_all"]
    max_items = f["max_items"]

    conn = get_conn()
    cur = conn.cursor()

    base_where = [
        "(isbn IS NULL OR isbn < %s OR isbn > %s)",
        "(isbn IS NULL OR isbn <> 111)",
    ]
    base_params = [ISBN_MIN, ISBN_MAX]

    if statuses_only:
        placeholders = ",".join(["%s"] * len(statuses_only))
        base_where.append(f"status IN ({placeholders})")
        base_params.extend(statuses_only)

    if include_null:
        base_where.append("(status IS NULL OR status = '')")

    if isbn_ok == 'valid':
        base_where.append("(isbn BETWEEN %s AND %s)")
        base_params.extend([ISBN_MIN, ISBN_MAX])

    where_sql = " AND ".join(base_where)

    total = _count_where(conn, "items_meli", where_sql, base_params)
    if not process_all:
        total = min(total, batch_size)
    total = min(total, max_items)
    job["total"] = total

    try:
        processed = 0
        ok = 0
        bad = 0

        while processed < total:
            cur.execute(f"""
                SELECT idml
                FROM items_meli
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT %s
            """, base_params + [min(batch_size, total - processed)])
            ids = [row[0] for row in cur.fetchall() if row and row[0]]
            if not ids:
                break

            for idml in ids:
                js, code = _get_ml_item_raw_backoff(idml, max_retries=5)
                job["last_idml"] = idml
                job["last_code"] = code

                if code == 200:
                    got = _extract_gtin_from_item_json(js or {})
                    if got is not None:
                        new_isbn = int(got)
                        ok += 1
                    else:
                        new_isbn = 111
                        bad += 1
                elif code in (404, 401, 403, 0, 429, 500, 503, 502):
                    new_isbn = 111
                    bad += 1
                else:
                    conn.commit()
                    cur.close()
                    job["state"] = "error"
                    job["unexpected"] = True
                    job["unexpected_code"] = code
                    job["unexpected_idml"] = idml
                    job["finished_at"] = time.time()
                    return

                try:
                    cur.execute("""
                        UPDATE items_meli
                        SET isbn = %s, last_update_idml_catalog = NOW()
                        WHERE idml = %s
                    """, (new_isbn, idml))
                except Exception:
                    bad += 1

                processed += 1
                job["processed"] = processed
                job["ok"] = ok
                job["code"] = bad

                if processed >= total:
                    break

            conn.commit()

        cur.close()
        job["state"] = "done"
        job["finished_at"] = time.time()
    except Exception as e:
        try:
            cur.close()
        except Exception:
            pass
        job["state"] = "error"
        job["message"] = f"{type(e).__name__}: {e}"
        job["finished_at"] = time.time()


def _run_job_verify(job_id):
    job = JOBS.get(job_id)
    if not job:
        return
    job["state"] = "running"
    job["started_at"] = time.time()

    f = JOBS[job_id]["filters"]
    isbn_ok = f["isbn_ok"]
    include_null = f["include_null"]
    statuses_only = f["statuses_only"]
    batch_size = f["batch_size"]
    process_all = f["process_all"]
    max_items = f["max_items"]

    conn = get_conn()
    cur = conn.cursor()

    where_clauses = []
    params = []

    if statuses_only:
        placeholders = ",".join(["%s"] * len(statuses_only))
        where_clauses.append(f"status IN ({placeholders})")
        params.extend(statuses_only)

    if include_null:
        where_clauses.append("(status IS NULL OR status = '')")

    if isbn_ok == 'valid':
        where_clauses.append("(isbn BETWEEN %s AND %s)")
        params.extend([ISBN_MIN, ISBN_MAX])
    elif isbn_ok == 'invalid':
        where_clauses.append("(isbn IS NULL OR isbn < %s OR isbn > %s)")
        params.extend([ISBN_MIN, ISBN_MAX])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    total = _count_where(conn, "items_meli", where_sql, params)
    if not process_all:
        total = min(total, batch_size)
    total = min(total, max_items)
    job["total"] = total

    try:
        processed = 0
        ok = 0
        code_cnt = 0

        while processed < total:
            cur.execute(f"""
                SELECT idml
                FROM items_meli
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT %s
            """, params + [min(batch_size, total - processed)])
            ids = [row[0] for row in cur.fetchall() if row and row[0]]
            if not ids:
                break

            for idml in ids:
                js, code = _get_ml_item_raw_backoff(idml, max_retries=5)
                job["last_idml"] = idml
                job["last_code"] = code

                if code == 200:
                    api_status = (js or {}).get("status")
                    new_status = api_status if isinstance(api_status, str) and api_status else "200"
                    if new_status == "200":
                        code_cnt += 1
                    else:
                        ok += 1
                elif code == 404:
                    new_status = "404"
                    code_cnt += 1
                elif code in (429, 500, 503, 502, 401, 403):
                    new_status = str(code)
                    code_cnt += 1
                elif code == 0:
                    new_status = "ERR"
                    code_cnt += 1
                else:
                    conn.commit()
                    cur.close()
                    job["state"] = "error"
                    job["unexpected"] = True
                    job["unexpected_code"] = code
                    job["unexpected_idml"] = idml
                    job["finished_at"] = time.time()
                    return

                try:
                    cur.execute("""
                        UPDATE items_meli
                        SET status = %s
                        WHERE idml = %s
                    """, (new_status, idml))
                except Exception:
                    code_cnt += 1

                processed += 1
                job["processed"] = processed
                job["ok"] = ok
                job["code"] = code_cnt

                if processed >= total:
                    break

            conn.commit()

        cur.close()
        job["state"] = "done"
        job["finished_at"] = time.time()
    except Exception as e:
        try:
            cur.close()
        except Exception:
            pass
        job["state"] = "error"
        job["message"] = f"{type(e).__name__}: {e}"
        job["finished_at"] = time.time()


