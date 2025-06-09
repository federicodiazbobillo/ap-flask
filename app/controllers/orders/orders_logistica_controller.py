from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

def _fetch_orders(id_param=None):
    """
    Función interna para obtener órdenes con filtros y datos asociados.
    """
    conn = get_conn()
    cursor = conn.cursor()

    # Construir condiciones de filtro
    filters = []
    params = []
    if id_param:
        filters.append("(o.order_id = %s OR o.pack_id = %s)")
        params.extend([id_param, id_param])

    # Consulta principal
    base_query = """
        SELECT o.order_id,
               o.pack_id,
               o.created_at,
               o.total_amount,
               o.status               AS order_status,
               o.manufacturing_ending_date,
               s.status               AS shipping_status
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
    """
    if filters:
        base_query += " WHERE " + " AND ".join(filters)
    base_query += " ORDER BY o.created_at DESC LIMIT 50"

    cursor.execute(base_query, tuple(params) if params else None)
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []
    for row in raw_orders:
        order_id, pack_id, created_at, total_amount, order_status, ending_date, shipping_status = row
        reference_id = pack_id or order_id
        created_str = created_at.strftime('%d/%m/%Y') if hasattr(created_at, 'strftime') else ''
        ending_str = ending_date.strftime('%d/%m/%Y') if hasattr(ending_date, 'strftime') else 'Entrega inmediata'
        orders.append({
            'order_id':                  order_id,
            'pack_id':                   pack_id,
            'reference_id':              reference_id,
            'created_at':                created_str,
            'total_amount':              total_amount,
            'status':                    order_status,
            'manufacturing_ending_date': ending_str,
            'shipping_status':           shipping_status
        })
        order_ids.append(order_id)

    # Obtener items relacionados
    items_map = {}
    if order_ids:
        placeholders = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity
            FROM order_items
            WHERE order_id IN ({placeholders})
        """, tuple(order_ids))
        for r in cursor.fetchall():
            items_map.setdefault(r[0], []).append({
                'order_id':   r[0],
                'item_id':    r[1],
                'seller_sku': r[2],
                'quantity':   r[3]
            })

    # Asignar items a cada orden
    for o in orders:
        o['items'] = items_map.get(o['order_id'], [])

    cursor.close()
    return orders

@orders_logistica_bp.route('/')
def index_logistica():
    """
    Vista HTML de logística con filtros.
    """
    id_param = request.args.get('id')
    orders = _fetch_orders(id_param)
    return render_template(
        'orders/logistica.html',
        ordenes=orders,
        tipo='logistica',
        filtro_id=id_param
    )

@orders_logistica_bp.route('/search')
def search_logistica():
    """
    Endpoint JSON para búsqueda de órdenes (AJAX).
    """
    id_param = request.args.get('id')
    orders = _fetch_orders(id_param)
    return jsonify({'orders': orders})
