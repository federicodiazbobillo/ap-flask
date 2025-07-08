# app/controllers/orders/orders_costos_controller.py

from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn
from app.integrations.apimongo.stock import obtener_stock_por_isbn, seleccionar_mejor_proveedor

orders_costos_bp = Blueprint('orders_costos', __name__, url_prefix='/orders/costos')

@orders_costos_bp.route('/')
def index_costos():
    conn = get_conn()
    cursor = conn.cursor()

    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')

    filters = []
    params = []

    if fecha_desde:
        filters.append("DATE(o.created_at) >= %s")
        params.append(fecha_desde)

    if fecha_hasta:
        filters.append("DATE(o.created_at) <= %s")
        params.append(fecha_hasta)

    status = request.args.get('status')

    if status == 'otros':
        filters.append("o.status NOT IN (%s, %s)")
        params.extend(['paid', 'cancelled'])
    elif status:
        filters.append("o.status = %s")
        params.append(status)

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    query = f"""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        {where_clause}
        ORDER BY o.created_at DESC
    """
    # Agregar límite solo si no hay filtros
    if not filters:
        query += " LIMIT 50"

    cursor.execute(query, tuple(params))
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

    # Cargar ítems
    items_map = {}
    if order_ids:
        placeholders = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({placeholders})
        """, tuple(order_ids))
        for r in cursor.fetchall():
            item = {
                'order_id':           r[0],
                'item_id':            r[1],
                'seller_sku':         r[2],
                'quantity':           r[3],
                'manufacturing_days': r[4],
                'sale_fee':           r[5],
            }
            items_map.setdefault(r[0], []).append(item)

    # Adjuntar ítems y calcular métricas
    total_neto_acumulado = 0
    total_items = 0
    total_ordenes = len(orders)

    for order in orders:

        order['items'] = items_map.get(order['order_id'], [])
        comision_total = sum(item['sale_fee'] * item['quantity'] for item in order['items'])
        envio = order['shipping']['list_cost'] or 0
        valor_neto = order['total_amount'] - comision_total - envio
        order['valor_neto'] = valor_neto
        total_neto_acumulado += valor_neto

        cantidad_items = sum(item['quantity'] for item in order['items'])
        order['cantidad_items'] = cantidad_items
        total_items += cantidad_items
        # Buscamos en mongo
        if order['items']:
            primer_isbn = order['items'][0]['seller_sku']
            raw_stock_info = obtener_stock_por_isbn(primer_isbn)
            if raw_stock_info:
                order['stock_info'] = seleccionar_mejor_proveedor(raw_stock_info)
            else:
                order['stock_info'] = {"proveedor": "❌", "stock": None, "precio": None}
        else:
            order['stock_info'] = {"proveedor": "❌", "stock": None, "precio": None}

    cursor.close()
    return render_template(
        'orders/costos.html',
        ordenes=orders,
        tipo='costos',
        total_neto=total_neto_acumulado,
        total_ordenes=total_ordenes,
        total_items=total_items,
        filtro_fecha_desde=fecha_desde,
        filtro_fecha_hasta=fecha_hasta,
        filtro_status=status
    )



@orders_costos_bp.route('/search')
def search_costos():
    conn = get_conn()
    cursor = conn.cursor()

    order_id = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    status = request.args.get('status')

    if order_id:
        # Buscar por ID puntual
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

        # Items de la orden
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

        # Calcular valor neto
        comision_total = sum(i['sale_fee'] * i['quantity'] for i in order['items'])
        envio = order['shipping']['list_cost'] or 0
        order['valor_neto'] = order['total_amount'] - comision_total - envio

        cursor.close()
        return jsonify({'orders': [order]})

    # 🔎 Filtros dinámicos
    filters = []
    params = []

    if fecha_desde:
        filters.append("DATE(o.created_at) >= %s")
        params.append(fecha_desde)

    if fecha_hasta:
        filters.append("DATE(o.created_at) <= %s")
        params.append(fecha_hasta)

    if status == 'otros':
        filters.append("o.status NOT IN (%s, %s)")
        params.extend(['paid', 'cancelled'])
    elif status:
        filters.append("o.status = %s")
        params.append(status)

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    # Obtener órdenes filtradas
    query = f"""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        {where_clause}
        ORDER BY o.created_at DESC
    """
    if not filters:
        query += " LIMIT 50"

    cursor.execute(query, tuple(params))
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

    # Traer ítems
    items_map = {}
    if order_ids:
        placeholders = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"""
            SELECT order_id, item_id, seller_sku, quantity, manufacturing_days, sale_fee
            FROM order_items
            WHERE order_id IN ({placeholders})
        """, tuple(order_ids))
        for r in cursor.fetchall():
            item = {
                'order_id':           r[0],
                'item_id':            r[1],
                'seller_sku':         r[2],
                'quantity':           r[3],
                'manufacturing_days': r[4],
                'sale_fee':           r[5],
            }
            items_map.setdefault(r[0], []).append(item)

    # Adjuntar ítems y calcular neto
    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])
        comision_total = sum(item['sale_fee'] * item['quantity'] for item in order['items'])
        envio = order['shipping']['list_cost'] or 0
        order['valor_neto'] = order['total_amount'] - comision_total - envio

    cursor.close()
    return jsonify({'orders': orders})

