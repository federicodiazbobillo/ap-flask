# app/controllers/orders/orders_costos_controller.py

from flask import Blueprint, render_template
from app.db import get_conn

orders_costos_bp = Blueprint('orders_costos', __name__, url_prefix='/orders/costos')

@orders_costos_bp.route('/')
def index_costos():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_ordenes = cursor.fetchall()

    ordenes = []
    orden_ids = []

    for row in raw_ordenes:
        orden = {
            'order_id': row[0],
            'created_at': row[1],
            'total_amount': row[2],
            'status': row[3],
            'shipping_id': row[4],
            'shipping': {'list_cost': row[5]},
        }
        ordenes.append(orden)
        orden_ids.append(row[0])

    items_map = {}
    if orden_ids:
        format_strings = ','.join(['%s'] * len(orden_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(orden_ids))
        for row in cursor.fetchall():
            item = {
                'order_id': row[0],
                'item_id': row[1],
                'seller_sku': row[2],
                'quantity': row[3],
                'manufacturing_days': row[4],
                'sale_fee': row[5],
            }
            items_map.setdefault(row[0], []).append(item)

    for orden in ordenes:
        orden['items'] = items_map.get(orden['order_id'], [])

    cursor.close()
    return render_template('orders/costos.html', ordenes=ordenes, tipo='costos')
