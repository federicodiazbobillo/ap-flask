from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

def _fetch_orders(id_param=None, fecha_desde=None, fecha_hasta=None, venc_desde=None, venc_hasta=None):
    """
    Obtiene órdenes con filtros de ID, rango de creación y rango de vencimiento (inclusive),
    agrupa por pack_id (o order_id si pack_id es null) y normaliza datos.
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
    if venc_desde:
        filters.append("DATE(o.manufacturing_ending_date) >= %s")
        params.append(venc_desde)
    if venc_hasta:
        filters.append("DATE(o.manufacturing_ending_date) <= %s")
        params.append(venc_hasta)

    # Base de consulta incluyendo guía y nota
    base_query = (
        "SELECT o.order_id,"
        " o.pack_id,"
        " o.created_at,"
        " o.total_amount,"
        " o.status AS order_status,"
        " o.manufacturing_ending_date,"
        " s.status AS shipping_status,"
        " o.guia AS guia,"
        " o.notas AS nota"
        " FROM orders o"
        " LEFT JOIN shipments s ON o.shipping_id = s.shipping_id"
    )
    # Agregar WHERE si hay filtros 
    if filters:
        base_query += " WHERE " + " AND ".join(filters)
        base_query += " ORDER BY o.created_at DESC"
    else:
        base_query += " WHERE DATE(o.created_at) = CURDATE()"

    cursor.execute(base_query, tuple(params) if params else None)
    raw = cursor.fetchall()

    # Agrupar registros por reference_id
    groups = {}
    for row in raw:
        # Desempaquetar incluyendo guia y nota
        order_id, pack_id, created_at, total_amount, order_status, ending_date, shipping_status, guia, nota = row
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
                    'shipping_status': shipping_status,
                    'guia': guia,
                    'nota': nota
                },
                'order_ids': []
            }
        groups[reference_id]['order_ids'].append(order_id)

    # Obtener items para todos los order_ids
    items_map = {}
    if groups:
        order_ids = [oid for group in groups.values() for oid in group['order_ids']]
        format_ids = ','.join(['%s'] * len(order_ids))
        cursor.execute(
            f"SELECT order_id, item_id, seller_sku, quantity FROM order_items WHERE order_id IN ({format_ids})",
            tuple(order_ids)
        )
        for oid, item_id, sku, qty in cursor.fetchall():
            items_map.setdefault(oid, []).append({
                'item_id': item_id,
                'seller_sku': sku,
                'quantity': qty
            })

    # Construir lista final
    orders = []
    for group in groups.values():
        meta = group['meta']
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
    Vista HTML de logística con filtros por ID, creación y vencimiento.
    """
    id_param = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    venc_desde = request.args.get('venc_desde')
    venc_hasta = request.args.get('venc_hasta')
    orders = _fetch_orders(id_param, fecha_desde, fecha_hasta, venc_desde, venc_hasta)
    return render_template(
        'orders/logistica.html',
        ordenes=orders,
        tipo='logistica',
        filtro_id=id_param,
        filtro_fecha_desde=fecha_desde,
        filtro_fecha_hasta=fecha_hasta,
        filtro_venc_desde=venc_desde,
        filtro_venc_hasta=venc_hasta
    )

@orders_logistica_bp.route('/search')
def search_logistica():
    """
    Endpoint JSON para búsqueda de órdenes con filtros y agrupación.
    """
    id_param = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    venc_desde = request.args.get('venc_desde')
    venc_hasta = request.args.get('venc_hasta')
    orders = _fetch_orders(id_param, fecha_desde, fecha_hasta, venc_desde, venc_hasta)
    return jsonify({'orders': orders})
