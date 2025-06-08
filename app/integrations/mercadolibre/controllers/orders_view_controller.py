# app/integrations/mercadolibre/controllers/orders_view_controller.py
from flask import Blueprint, render_template
from app.db import get_conn

orders_view_bp = Blueprint('orders_view', __name__, url_prefix='/ordenes')

@orders_view_bp.route('/')
def index():
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    # Obtener las 50 órdenes más recientes
    cursor.execute("""
        SELECT o.*, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    ordenes = cursor.fetchall()

    # Obtener los IDs
    orden_ids = [o['order_id'] for o in ordenes]
    items_map = {}

    if orden_ids:
        format_strings = ','.join(['%s'] * len(orden_ids))
        query = f"SELECT * FROM order_items WHERE order_id IN ({format_strings})"
        cursor.execute(query, tuple(orden_ids))
        items = cursor.fetchall()

        for item in items:
            items_map.setdefault(item['order_id'], []).append(item)

    # Asociar ítems y envío
    for orden in ordenes:
        orden['items'] = items_map.get(orden['order_id'], [])
        orden['shipping'] = {
            "list_cost": orden.pop('list_cost', None)
        }

    cursor.close()
    print("▶️ Órdenes totales:", len(ordenes))
    print("▶️ Primera orden:", ordenes[0] if ordenes else "Ninguna")
    return render_template('orders/index.html', ordenes=ordenes)

