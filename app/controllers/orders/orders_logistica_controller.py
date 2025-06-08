# app/controllers/orders/orders_logistica_controller.py

from flask import Blueprint, render_template
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

@orders_logistica_bp.route('/')
def index_logistica():
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.*, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    ordenes = cursor.fetchall()

    orden_ids = [o['order_id'] for o in ordenes]
    items_map = {}

    if orden_ids:
        cursor.execute("""
            SELECT * FROM order_items
            WHERE order_id IN ({})
        """.format(','.join(['%s'] * len(orden_ids))), orden_ids)
        items = cursor.fetchall()
        for item in items:
            items_map.setdefault(item['order_id'], []).append(item)

    for orden in ordenes:
        orden['items'] = items_map.get(orden['order_id'], [])
        orden['shipping'] = {
            "list_cost": orden.pop('list_cost', None)
        }

    cursor.close()
    return render_template('orders/logistica.html', ordenes=ordenes, tipo='logistica')
