# app/controllers/items/mercadolibre/sync_celesa/parametros_sale_terms_celesa.py
from flask import render_template, request, redirect, url_for, flash, jsonify

# Obtener el blueprint sin exponerlo a nivel de módulo
def _bp():
    from .index import sync_celesa_bp
    return sync_celesa_bp

# Conexión (tu helper real)
from app.db import get_conn

ALLOWED_ACTIONS = {"publicar", "pausar"}

# ------------------- Helpers DB -------------------
def _safe_ping(conn):
    """Intenta reconectar si la conexión se cayó (MySQLdb/PyMySQL)."""
    try:
        conn.ping(reconnect=True)
    except Exception:
        pass

def _rows_to_dicts(rows, cols):
    """Convierte filas (tuplas) en lista de dicts con columnas dadas."""
    out = []
    for r in rows:
        out.append({c: r[i] for i, c in enumerate(cols)})
    return out

# ------------------- DDL -------------------
def ensure_table():
    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sale_terms_celesa (
              id INT AUTO_INCREMENT PRIMARY KEY,
              provider VARCHAR(100) NOT NULL DEFAULT 'celesa',
              max_stock INT NOT NULL,
              action VARCHAR(50) NOT NULL,
              delivery_days INT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        # índices (ignorar si ya existen)
        try:
            cur.execute("CREATE INDEX idx_stc_provider ON sale_terms_celesa (provider)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX idx_stc_max ON sale_terms_celesa (max_stock)")
        except Exception:
            pass
        conn.commit()
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

# ------------------- Validación -------------------
def _validate(provider, max_stock, action, delivery_days):
    errs = []
    if not provider:
        errs.append("provider es requerido.")
    try:
        max_stock = int(max_stock)
        if max_stock < 0:
            errs.append("max_stock debe ser >= 0.")
    except Exception:
        errs.append("max_stock debe ser numérico.")
    if action not in ALLOWED_ACTIONS:
        errs.append(f"action inválida. Usa: {', '.join(sorted(ALLOWED_ACTIONS))}")
    try:
        delivery_days = int(delivery_days)
        if delivery_days < 15:
            errs.append("delivery_days debe ser >= 15.")
    except Exception:
        errs.append("delivery_days debe ser numérico.")
    return errs

# ------------------- UI -------------------
@_bp().route('/sale-terms', methods=['GET'])
def sale_terms_index():
    ensure_table()
    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        # Selección explícita de columnas para orden fijo
        cols = ["id", "provider", "max_stock", "action", "delivery_days", "created_at", "updated_at"]
        cur.execute("""
            SELECT id, provider, max_stock, action, delivery_days, created_at, updated_at
            FROM sale_terms_celesa
            ORDER BY provider ASC, max_stock ASC
        """)
        rows = cur.fetchall()  # tuplas
        rows_dict = _rows_to_dicts(rows, cols)  # opcional: para que el template use keys
        return render_template(
            'items/mercadolibre/sync_celesa/parametros_sale_terms_celesa.html',
            rows=rows_dict,
            allowed_actions=sorted(ALLOWED_ACTIONS)
        )
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

@_bp().route('/sale-terms/create', methods=['POST'])
def sale_terms_create():
    provider = (request.form.get('provider') or 'celesa').strip()
    max_stock = request.form.get('max_stock')
    action = request.form.get('action')
    delivery_days = request.form.get('delivery_days')

    errs = _validate(provider, max_stock, action, delivery_days)
    if errs:
        for e in errs:
            flash(e, 'danger')
        return redirect(url_for('sync_celesa_bp.sale_terms_index'))

    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO sale_terms_celesa (provider, max_stock, action, delivery_days)
            VALUES (%s, %s, %s, %s)
        """, (provider, int(max_stock), action, int(delivery_days)))
        conn.commit()
        flash("Regla creada.", "success")
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

@_bp().route('/sale-terms/update/<int:row_id>', methods=['POST'])
def sale_terms_update(row_id):
    provider = (request.form.get('provider') or 'celesa').strip()
    max_stock = request.form.get('max_stock')
    action = request.form.get('action')
    delivery_days = request.form.get('delivery_days')

    errs = _validate(provider, max_stock, action, delivery_days)
    if errs:
        for e in errs:
            flash(e, 'danger')
        return redirect(url_for('sync_celesa_bp.sale_terms_index'))

    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE sale_terms_celesa
            SET provider=%s, max_stock=%s, action=%s, delivery_days=%s
            WHERE id=%s
        """, (provider, int(max_stock), action, int(delivery_days), row_id))
        conn.commit()
        flash("Regla actualizada.", "success")
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

@_bp().route('/sale-terms/delete/<int:row_id>', methods=['POST'])
def sale_terms_delete(row_id):
    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM sale_terms_celesa WHERE id=%s", (row_id,))
        conn.commit()
        flash("Regla eliminada.", "warning")
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

# ------------------- API (para modal) -------------------
@_bp().route('/sale-terms/get/<int:row_id>', methods=['GET'])
def sale_terms_get(row_id):
    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, provider, max_stock, action, delivery_days
            FROM sale_terms_celesa
            WHERE id=%s
        """, (row_id,))
        row = cur.fetchone()  # tupla
        if not row:
            return jsonify({"error": "not_found"}), 404
        cols = ["id", "provider", "max_stock", "action", "delivery_days"]
        row_dict = {c: row[i] for i, c in enumerate(cols)}
        return jsonify(row_dict)
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass

# ------------------- Helper interno -------------------
def get_sale_term_for_stock(stock, provider='celesa'):
    """
    Devuelve la regla aplicable como dict (o None).
    Rangos: 0..max1, (max1+1)..max2, ...
    """
    if stock is None:
        stock = 0
    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, provider, max_stock, action, delivery_days
            FROM sale_terms_celesa
            WHERE provider=%s
            ORDER BY max_stock ASC
        """, (provider,))
        cols = ["id", "provider", "max_stock", "action", "delivery_days"]
        for row in cur.fetchall():  # tuplas
            # max_stock es la 3ra columna (índice 2)
            if stock <= int(row[2]):
                return {c: row[i] for i, c in enumerate(cols)}
        return None
    finally:
        try: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass
