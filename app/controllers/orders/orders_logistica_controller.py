from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

@orders_logistica_bp.route('/')
def index_logistica():
    # Conexión y cursor
    conn = get_conn()
    cursor = conn.cursor()

    # Selección de campos: incluidos pack_id, manufacturing_ending_date y estado de envío
    cursor.execute("""
        SELECT o.order_id,
               o.pack_id,
               o.created_at,
               o.total_amount,
               o.status       AS order_status,
               o.manufacturing_ending_date,
               s.status       AS shipping_status
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []

    # Construir lista de órdenes con reference_id, formatear fechas y mapear estado de envío
    for row in raw_orders:
        order_id     = row[0]
        pack_id      = row[1]
        reference_id = pack_id if pack_id is not None else order_id

        # Formatear created_at y manufacturing_ending_date
        created_at   = row[2]
        created_str  = created_at.strftime('%d/%m/%Y') if hasattr(created_at, 'strftime') else ''
        ending_date  = row[5]
        ending_str   = ending_date.strftime('%d/%m/%Y') if hasattr(ending_date, 'strftime') else 'Entrega inmediata'

        order = {
            'order_id': order_id,
            'pack_id': pack_id,
            'reference_id': reference_id,
            'created_at': created_str,
            'total_amount': row[3],
            'status': row[4],             # status de la orden
            'manufacturing_ending_date': ending_str,
            'shipping_status': row[6]     # estado del envío
        }
        orders.append(order)
        order_ids.append(order_id)

    # Obtener items por order_id (solo campos necesarios)
    items_map = {}
    if order_ids:
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(order_ids))
        for item_row in cursor.fetchall():
            item = {
                'order_id':   item_row[0],
                'item_id':    item_row[1],
                'seller_sku': item_row[2],
                'quantity':   item_row[3],
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
        # Búsqueda por order_id o pack_id, incluyendo estado de envío
        cursor.execute("""
            SELECT o.order_id,
                   o.pack_id,
                   o.created_at,
                   o.total_amount,
                   o.status       AS order_status,
                   o.manufacturing_ending_date,
                   s.status       AS shipping_status
            FROM orders o
            LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
            WHERE o.order_id = %s OR o.pack_id = %s
            LIMIT 1
        """, (order_id_param, order_id_param))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            return jsonify({'message': 'Order not found'}), 404

        order_id     = row[0]
        pack_id      = row[1]
        reference_id = pack_id if pack_id is not None else order_id

        # Formatear fechas
        created_at   = row[2]
        created_str  = created_at.strftime('%d/%m/%Y') if hasattr(created_at, 'strftime') else ''
        ending_date  = row[5]
        ending_str   = ending_date.strftime('%d/%m/%Y') if hasattr(ending_date, 'strftime') else 'Entrega inmediata'

        order = {
            'order_id':                 order_id,
            'pack_id':                  pack_id,
            'reference_id':             reference_id,
            'created_at':               created_str,
            'total_amount':             row[3],
            'status':                   row[4],
            'manufacturing_ending_date': ending_str,
            'shipping_status':           row[6]
        }

        # Items para la orden específica (solo campos necesarios)
        cursor.execute("""
            SELECT order_id, item_id, seller_sku, quantity
            FROM order_items
            WHERE order_id = %s
        """, (order['order_id'],))
        order['items'] = [
            {
                'order_id':   r[0],
                'item_id':    r[1],
                'seller_sku': r[2],
                'quantity':   r[3],
            }
            for r in cursor.fetchall()
        ]

        cursor.close()
        return jsonify({'orders': [order]})

    # Sin filtros: últimas 50 órdenes con estado de envío
    cursor.execute("""
        SELECT o.order_id,
               o.pack_id,
               o.created_at,
               o.total_amount,
               o.status       AS order_status,
               o.manufacturing_ending_date,
               s.status       AS shipping_status
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []

    for row in raw_orders:
        order_id     = row[0]
        pack_id      = row[1]
        reference_id = pack_id if pack_id is not None else order_id

        # Formatear fechas
        created_at   = row[2]
        created_str  = created_at.strftime('%d/%m/%Y') if hasattr(created_at, 'strftime') else ''
        ending_date  = row[5]
        ending_str   = ending_date.strftime('%d/%m/%Y') if hasattr(ending_date, 'strftime') else 'Entrega inmediata'

        order = {
            'order_id':                 order_id,
            'pack_id':                  pack_id,
            'reference_id':             reference_id,
            'created_at':               created_str,
            'total_amount':             row[3],
            'status':                   row[4],
            'manufacturing_ending_date': ending_str,
            'shipping_status':           row[6]
        }
        orders.append(order)
        order_ids.append(order_id)

    items_map = {}
    if order_ids:
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity
            FROM order_items
            WHERE order_id IN ({format_strings})
        """, tuple(order_ids))
        for item_row in cursor.fetchall():
            item = {
                'order_id':   item_row[0],
                'item_id':    item_row[1],
                'seller_sku': item_row[2],
                'quantity':   item_row[3],
            }
            items_map.setdefault(item_row[0], []).append(item)

    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

    cursor.close()
    return jsonify({'orders': orders})
