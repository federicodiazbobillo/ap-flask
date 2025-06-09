from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

@orders_logistica_bp.route('/')
def index_logistica():
    # Conexión y cursor
    conn = get_conn()
    cursor = conn.cursor()

    # Selección de campos incluyendo pack_id y manufacturing_ending_date
    cursor.execute("""
        SELECT o.order_id, o.pack_id, o.created_at, o.total_amount, o.status, o.manufacturing_ending_date
        FROM orders o
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []

    # Construir lista de órdenes con reference_id
    for row in raw_orders:
        order_id = row[0]
        pack_id = row[1]
        reference_id = pack_id if pack_id is not None else order_id
        # Manejar campo que puede ser NULL
        ending_date = row[5] if row[5] is not None else ''
        order = {
            'order_id': order_id,
            'pack_id': pack_id,
            'reference_id': reference_id,
            'created_at': row[2],
            'total_amount': row[3],
            'status': row[4],
            'manufacturing_ending_date': ending_date,
        }
        orders.append(order)
        order_ids.append(order_id)

    # Obtener items por order_id
    items_map = {}
    if order_ids:
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(order_ids))
        for item_row in cursor.fetchall():
            item = {
                'order_id': item_row[0],
                'item_id': item_row[1],
                'seller_sku': item_row[2],
                'quantity': item_row[3],
                'manufacturing_days': item_row[4],
                'sale_fee': item_row[5],
            }
            items_map.setdefault(item_row[0], []).append(item)

    # Añadir items a cada orden
    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return render_template('orders/logistica.html', ordenes=orders, tipo='logistica')


@orders_logistica_bp.route('/search')
def search_orders():
    # Conexión y cursor
    conn = get_conn()
    cursor = conn.cursor()

    order_id_param = request.args.get('id')

    if order_id_param:
        # Búsqueda por order_id o pack_id
        cursor.execute("""
            SELECT o.order_id, o.pack_id, o.created_at, o.total_amount, o.status, o.manufacturing_ending_date
            FROM orders o
            WHERE o.order_id = %s OR o.pack_id = %s
            LIMIT 1
        """, (order_id_param, order_id_param))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            return jsonify({'message': 'Order not found'}), 404

        order_id = row[0]
        pack_id = row[1]
        reference_id = pack_id if pack_id is not None else order_id
        ending_date = row[5] if row[5] is not None else ''
        order = {
            'order_id': order_id,
            'pack_id': pack_id,
            'reference_id': reference_id,
            'created_at': row[2],
            'total_amount': row[3],
            'status': row[4],
            'manufacturing_ending_date': ending_date,
        }

        # Items para la orden específica
        cursor.execute("""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id = %s
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

    # Sin filtros: últimas 50 órdenes
    cursor.execute("""
        SELECT o.order_id, o.pack_id, o.created_at, o.total_amount, o.status, o.manufacturing_ending_date
        FROM orders o
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []

    for row in raw_orders:
        order_id = row[0]
        pack_id = row[1]
        reference_id = pack_id if pack_id is not None else order_id
        ending_date = row[5] if row[5] is not None else ''
        order = {
            'order_id': order_id,
            'pack_id': pack_id,
            'reference_id': reference_id,
            'created_at': row[2],
            'total_amount': row[3],
            'status': row[4],
            'manufacturing_ending_date': ending_date,
        }
        orders.append(order)
        order_ids.append(order_id)

    items_map = {}
    if order_ids:
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(order_ids))
        for item_row in cursor.fetchall():
            item = {
                'order_id': item_row[0],
                'item_id': item_row[1],
                'seller_sku': item_row[2],
                'quantity': item_row[3],
                'manufacturing_days': item_row[4],
                'sale_fee': item_row[5],
            }
            items_map.setdefault(item_row[0], []).append(item)

    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return jsonify({'orders': orders})
