# app/controllers/orders/orders_costos_controller.py

from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_costos_bp = Blueprint('orders_costos', __name__, url_prefix='/orders/costos')


@orders_costos_bp.route('/')
def index_costos():
    conn = get_conn()
    cursor = conn.cursor()

    # Load latest 50 orders
    cursor.execute("""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []
    for row in raw_orders:
        order = {
            'order_id':    row[0],
            'created_at':  row[1],
            'total_amount': row[2],
            'status':      row[3],
            'shipping_id': row[4],
            'shipping':    {'list_cost': row[5]},
        }
        orders.append(order)
        order_ids.append(row[0])

    # Load items for those orders
    items_map = {}
    if order_ids:
        placeholders = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({placeholders})
        """, tuple(order_ids))
        for row in cursor.fetchall():
            item = {
                'order_id':           row[0],
                'item_id':            row[1],
                'seller_sku':         row[2],
                'quantity':           row[3],
                'manufacturing_days': row[4],
                'sale_fee':           row[5],
            }
            items_map.setdefault(row[0], []).append(item)

    # Attach items to each order
    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return render_template('orders/costos.html', orders=orders, tipo='costos')


@orders_costos_bp.route('/search')
def search_costos():
    conn = get_conn()
    cursor = conn.cursor()

    order_id = request.args.get('id')
    if order_id:
        # Search for a single order by order_id or pack_id
        cursor.execute("""
            SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
            FROM orders o
            LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
            WHERE o.order_id = %s OR o.pack_id = %s
            LIMIT 1
        """, (order_id, order_id))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            return jsonify({'orders': []}), 404

        order = {
            'order_id':    row[0],
            'created_at':  row[1],
            'total_amount': row[2],
            'status':      row[3],
            'shipping_id': row[4],
            'shipping':    {'list_cost': row[5]},
        }

        # Load items for this order
        cursor.execute("""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id = %s
        """, (order['order_id'],))
        items = cursor.fetchall()
        order['items'] = [
            {
                'order_id':           r[0],
                'item_id':            r[1],
                'seller_sku':         r[2],
                'quantity':           r[3],
                'manufacturing_days': r[4],
                'sale_fee':           r[5],
            }
            for r in items
        ]

        cursor.close()
        return jsonify({'orders': [order]})

    # No 'id' parameter: fall back to last 50 orders
    cursor.execute("""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []
    for row in raw_orders:
        order = {
            'order_id':    row[0],
            'created_at':  row[1],
            'total_amount': row[2],
            'status':      row[3],
            'shipping_id': row[4],
            'shipping':    {'list_cost': row[5]},
        }
        orders.append(order)
        order_ids.append(row[0])

    # Load items
    items_map = {}
    if order_ids:
        placeholders = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({placeholders})
        """, tuple(order_ids))
        for row in cursor.fetchall():
            item = {
                'order_id':           row[0],
                'item_id':            row[1],
                'seller_sku':         row[2],
                'quantity':           row[3],
                'manufacturing_days': row[4],
                'sale_fee':           row[5],
            }
            items_map.setdefault(row[0], []).append(item)

    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return jsonify({'orders': orders})
