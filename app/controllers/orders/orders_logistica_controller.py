from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')


@orders_logistica_bp.route('/')
def index_logistica():
    conn = get_conn()
    cursor = conn.cursor()

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
            'order_id': row[0],
            'created_at': row[1],
            'total_amount': row[2],
            'status': row[3],
            'shipping_id': row[4],
            'shipping': {'list_cost': row[5]},
        }
        orders.append(order)
        order_ids.append(row[0])

    items_map = {}
    if order_ids:
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(order_ids))
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

    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return render_template('orders/logistica.html', ordenes=orders, tipo='logistica')


@orders_logistica_bp.route('/search')
def search_orders():
    conn = get_conn()
    cursor = conn.cursor()

    order_id = request.args.get('id')

    if order_id:
        cursor.execute("""
            SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
            FROM orders o
            LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
            WHERE o.order_id = %s OR o.pack_id = %s
            LIMIT 1
        """, (order_id, order_id))
        row = cursor.fetchone()

        if not row:
            return jsonify({'message': 'Order not found'}), 404

        order = {
            'order_id': row[0],
            'created_at': row[1],
            'total_amount': row[2],
            'status': row[3],
            'shipping_id': row[4],
            'shipping': {'list_cost': row[5]},
        }

        cursor.execute("""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items WHERE order_id = %s
        """, (order['order_id'],))
        order['items'] = [
            {
                'order_id': r[0],
                'item_id': r[1],
                'seller_sku': r[2],
                'quantity': r[3],
                'manufacturing_days': r[4],
                'sale_fee': r[5],
            }
            for r in cursor.fetchall()
        ]

        cursor.close()
        return jsonify({'orders': [order]})

    # No filters: return last 50 orders
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
            'order_id': row[0],
            'created_at': row[1],
            'total_amount': row[2],
            'status': row[3],
            'shipping_id': row[4],
            'shipping': {'list_cost': row[5]},
        }
        orders.append(order)
        order_ids.append(row[0])

    items_map = {}
    if order_ids:
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(order_ids))
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

    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return jsonify({'orders': orders})
