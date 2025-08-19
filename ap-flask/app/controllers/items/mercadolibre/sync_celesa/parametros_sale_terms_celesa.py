# app/controllers/items/mercadolibre/sync_celesa/parametros_sale_terms_celesa.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from app.controllers.items.mercadolibre.sync_celesa.index import sync_celesa_bp

# ---- conexión MySQL ----
try:
    # si usás utils.db
    from utils.db import get_conn
except Exception:
    # si usás db.get_app_connection()
    from db import get_app_connection as get_conn

ALLOWED_ACTIONS = {"publicar", "pausar"}

# ---- helpers de cursores ----
def _dict_cursor(conn):
    """
    Devuelve un cursor que entrega dicts si es posible.
    Soporta mysql-connector (dictionary=True) y PyMySQL (DictCursor).
    """
    try:
        return conn.cursor(dictionary=True)  # mysql-connector
    except Exception:
        try:
            from pymysql.cursors import DictCursor  # PyMySQL
            return conn.cursor(DictCursor)
        except Exception:
            return conn.cursor()  # fallback a tuplas

# ---- helper: crear tabla si no existe ----
def ensure_table():
    conn = get_conn()
    cur = conn.cursor()
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
    # índices (compatibles con distintas versiones de MySQL/MariaDB)
    try:
        cur.execute("CREATE INDEX idx_stc_provider ON sale_terms_celesa (provider)")
    except Exception:
        pass
    try:
        cur.execute("CREATE INDEX idx_stc_max ON sale_terms_celesa (max_stock)")
    except Exception:
        pass
    conn.commit()
    cur.close()
    conn.close()

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

# ---------- UI ----------
@sync_celesa_bp.route('/sale-terms', methods=['GET'])
def sale_terms_index():
    ensure_table()
    conn = get_conn()
    cur = _dict_cursor(conn)
    cur.execute("SELECT * FROM sale_terms_celesa ORDER BY provider ASC, max_stock ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(
        'mercadolibre/sync_celesa/sale_terms_celesa.html',  # ruta de template corregida
        rows=rows,
        allowed_actions=sorted(ALLOWED_ACTIONS)
    )

@sync_celesa_bp.route('/sale-terms/create', methods=['POST'])
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
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sale_terms_celesa (provider, max_stock, action, delivery_days)
        VALUES (%s, %s, %s, %s)
    """, (provider, int(max_stock), action, int(delivery_days)))
    conn.commit()
    cur.close()
    conn.close()
    flash("Regla creada.", "success")
    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

@sync_celesa_bp.route('/sale-terms/update/<int:row_id>', methods=['POST'])
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
    cur = conn.cursor()
    cur.execute("""
        UPDATE sale_terms_celesa
        SET provider=%s, max_stock=%s, action=%s, delivery_days=%s
        WHERE id=%s
    """, (provider, int(max_stock), action, int(delivery_days), row_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Regla actualizada.", "success")
    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

@sync_celesa_bp.route('/sale-terms/delete/<int:row_id>', methods=['POST'])
def sale_terms_delete(row_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM sale_terms_celesa WHERE id=%s", (row_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Regla eliminada.", "warning")
    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

# ---------- API para modal ----------
@sync_celesa_bp.route('/sale-terms/get/<int:row_id>', methods=['GET'])
def sale_terms_get(row_id):
    conn = get_conn()
    cur = _dict_cursor(conn)
    cur.execute("""
        SELECT id, provider, max_stock, action, delivery_days
        FROM sale_terms_celesa
        WHERE id=%s
    """, (row_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(row)

# ---------- Helper para usar en el sync ----------
def get_sale_term_for_stock(stock, provider='celesa'):
    """
    Devuelve el dict de la regla aplicable (o None).
    Rangos: 0..max1, (max1+1)..max2, ...
    """
    if stock is None:
        stock = 0
    conn = get_conn()
    cur = _dict_cursor(conn)
    cur.execute("""
        SELECT * FROM sale_terms_celesa
        WHERE provider=%s
        ORDER BY max_stock ASC
    """, (provider,))
    for row in cur.fetchall():
        # stock <= tope del rango
        try:
            if stock <= int(row['max_stock'] if isinstance(row, dict) else row[2]):
                cur.close()
                conn.close()
                return row
        except Exception:
            # si el cursor no es dict, row[2] corresponde a max_stock según el SELECT *
            if stock <= row[2]:
                cur.close()
                conn.close()
                return row
    cur.close()
    conn.close()
    return None
