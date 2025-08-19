# app/controllers/items/mercadolibre/sync_celesa/parametros_sale_terms_celesa.py
from flask import render_template, request, redirect, url_for, flash, jsonify

def _bp():
    from .index import sync_celesa_bp
    return sync_celesa_bp

from app.db import get_conn

ALLOWED_ACTIONS = {"publicar", "pausar"}

# --- helpers ---
def _safe_ping(conn):
    try:
        conn.ping(reconnect=True)
    except Exception:
        pass

def _rows_to_dicts(rows, cols):
    return [{c: r[i] for i, c in enumerate(cols)} for r in rows]

# ---------- SOLO LECTURA ----------
@_bp().route('/sale-terms', methods=['GET'])
def sale_terms_index():
    conn = get_conn()
    _safe_ping(conn)
    cur = conn.cursor()
    try:
        cols = ["id", "provider", "max_stock", "action", "delivery_days", "created_at", "updated_at"]
        cur.execute("""
            SELECT id, provider, max_stock, action, delivery_days, created_at, updated_at
            FROM sale_terms_celesa
            ORDER BY provider ASC, max_stock ASC
        """)
        rows = _rows_to_dicts(cur.fetchall(), cols)
        return render_template(
            'items/mercadolibre/sync_celesa/parametros_sale_terms_celesa.html',
            rows=rows,
            allowed_actions=sorted(ALLOWED_ACTIONS),
        )
    finally:
        try: cur.close()
        except Exception: pass
        # NO cerrar conn: la cierra Flask en teardown

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
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not_found"}), 404
        cols = ["id", "provider", "max_stock", "action", "delivery_days"]
        return jsonify({c: row[i] for i, c in enumerate(cols)})
    finally:
        try: cur.close()
        except Exception: pass
        # NO cerrar conn

# ---------- STUBS (sin escritura) ----------
@_bp().route('/sale-terms/create', methods=['POST'])
def sale_terms_create():
    flash("Modo solo lectura: no se puede crear.", "warning")
    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

@_bp().route('/sale-terms/update/<int:row_id>', methods=['POST'])
def sale_terms_update(row_id):
    flash("Modo solo lectura: no se puede actualizar.", "warning")
    return redirect(url_for('sync_celesa_bp.sale_terms_index'))

@_bp().route('/sale-terms/delete/<int:row_id>', methods=['POST'])
def sale_terms_delete(row_id):
    flash("Modo solo lectura: no se puede eliminar.", "warning")
    return redirect(url_for('sync_celesa_bp.sale_terms_index'))
