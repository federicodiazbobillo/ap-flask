from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn
from app.utils.filters.query_builder import construir_consulta
#from app.utils.filters.core.filtro_por_id_o_pack import filtro_por_id_o_pack

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
    return render_template('orders/logistica.html', ordenes=ordenes, tipo='logistica')


@orders_logistica_bp.route('/buscar')
def buscar_order_logistica():
    valor = request.args.get('id')
    if not valor:
        return jsonify({'error': 'Falta el parámetro id'}), 400

    filtros = [lambda: filtro_por_id_o_pack(valor)]
    where_clause, params = construir_consulta(filtros)

    conn = get_conn()
    cursor = conn.cursor()

    sql = f"""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        WHERE {where_clause}
        LIMIT 1
    """
    cursor.execute(sql, params)
    row = cursor.fetchone()

    if not row:
        return jsonify({'mensaje': 'No se encontró el pedido con ese ID o pack_id'}), 404

    orden = {
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
    """, (orden['order_id'],))
    items = cursor.fetchall()

    orden['items'] = [{
        'order_id': r[0],
        'item_id': r[1],
        'seller_sku': r[2],
        'quantity': r[3],
        'manufacturing_days': r[4],
        'sale_fee': r[5],
    } for r in items]

    cursor.close()
    return jsonify({'order': orden})
