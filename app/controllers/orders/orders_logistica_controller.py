from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

def _fetch_orders(id_param=None, fecha_desde=None, fecha_hasta=None):
    """
    Función interna para obtener órdenes con filtros de ID y rango de fechas (inclusive),
    agrupar por pack_id (o order_id si pack_id es null) y normalizar datos.
    """
    conn = get_conn()
    cursor = conn.cursor()

    # Construir condiciones de filtro
    filters = []
    params = []
    if id_param:
        filters.append("(o.order_id = %s OR o.pack_id = %s)")
        params.extend([id_param, id_param])
    if fecha_desde:
        filters.append("DATE(o.created_at) >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        filters.append("DATE(o.created_at) <= %s")
        params.append(fecha_hasta)

    # Consulta base con JOIN para estado de envío
    base_query = (
        "SELECT o.order_id,"
        " o.pack_id,"
        " o.created_at,"
        " o.total_amount,"
        " o.status AS order_status,"
        " o.manufacturing_ending_date,"
        " s.status AS shipping_status"
        " FROM orders o"
        " LEFT JOIN shipments s ON o.shipping_id = s.shipping_id"
    )
    if filters:
        base_query += " WHERE " + " AND ".join(filters)
    else:
        base_query += " ORDER BY o.created_at DESC LIMIT 50"
    # Si hay filtros, ordenar sin límite
    if filters:
        base_query += " ORDER BY o.created_at DESC"

    cursor.execute(base_query, tuple(params) if params else None)
    raw = cursor.fetchall()

    # Agrupar registros por reference_id = pack_id o order_id
    groups = {}  # reference_id -> {'meta': {...}, 'order_ids': []}
    for row in raw:
        order_id, pack_id, created_at, total_amount, order_status, ending_date, shipping_status = row
        reference_id = pack_id or order_id
        if reference_id not in groups:
            created_str = created_at.strftime('%d/%m/%Y') if hasattr(created_at, 'strftime') else ''
            ending_str = ending_date.strftime('%d/%m/%Y') if hasattr(ending_date, 'strftime') else 'Entrega inmediata'
            groups[reference_id] = {
                'meta': {
                    'reference_id': reference_id,
                    'created_at': created_str,
                    'total_amount': total_amount,
                    'status': order_status,
                    'manufacturing_ending_date': ending_str,
                    'shipping_status': shipping_status
                },
                'order_ids': []
            }
        groups[reference_id]['order_ids'].append(order_id)

    # Obtener items relacionados para todos los order_ids
    all_ids = [oid for g in groups.values() for oid in g['order_ids']]
    items_map = {}
    if all_ids:
        placeholders = ','.join(['%s'] * len(all_ids))
        cursor.execute(
            f"SELECT order_id, item_id, seller_sku, quantity"
            f" FROM order_items WHERE order_id IN ({placeholders})",
            tuple(all_ids)
        )
        for r in cursor.fetchall():
            items_map.setdefault(r[0], []).append({
                'item_id': r[1],
                'seller_sku': r[2],
                'quantity': r[3]
            })

    # Construir lista final con items agrupados
    orders = []
    for gid, group in groups.items():
        meta = group['meta']
        # Consolidar todos los items de los order_ids del grupo
        items = []
        for oid in group['order_ids']:
            items.extend(items_map.get(oid, []))
        meta['items'] = items
        orders.append(meta)

    cursor.close()
    return orders

@orders_logistica_bp.route('/')
def index_logistica():
    """
    Vista HTML de logística con filtros y agrupación por pack.
    """
    id_param = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    orders = _fetch_orders(id_param, fecha_desde, fecha_hasta)
    return render_template(
        'orders/logistica.html',
        ordenes=orders,
        tipo='logistica',
        filtro_id=id_param,
        filtro_fecha_desde=fecha_desde,
        filtro_fecha_hasta=fecha_hasta
    )

@orders_logistica_bp.route('/search')
def search_logistica():
    """
    Endpoint JSON para búsqueda de órdenes con filtros y agrupación.
    """
    id_param = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    orders = _fetch_orders(id_param, fecha_desde, fecha_hasta)
    return jsonify({'orders': orders})
