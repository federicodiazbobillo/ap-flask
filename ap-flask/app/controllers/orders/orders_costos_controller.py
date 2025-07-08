# app/controllers/orders/orders_costos_controller.py
import pprint
from decimal import Decimal
from flask import Blueprint, render_template, request
from app.db import get_conn
from app.integrations.apimongo.stock import obtener_stock_por_lote, seleccionar_mejor_proveedor

# 💱 Variables de conversión (luego serán dinámicas)
TipoDeCambioMXNEUR = 22
fleteInternacional = 1.25

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
    if not filters:
        query += " LIMIT 50"

    cursor.execute(query, tuple(params))
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []
    total_ventas_mxn = 0  # 🧮 Acumulador para total de ventas

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
        total_ventas_mxn += row[2] or 0  # 🔄 Acumular venta

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

    total_neto_acumulado = 0
    total_items = 0
    total_ordenes = len(orders)
    total_rentabilidad_mxn = Decimal('0.00')
    total_costo_estimado = Decimal('0.00')

    all_isbns = set()
    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])
        for item in order['items']:
            if item['seller_sku']:
                all_isbns.add(item['seller_sku'])

    stock_data = obtener_stock_por_lote(list(all_isbns))

    for order in orders:
        comision_total = sum(item['sale_fee'] * item['quantity'] for item in order['items'])
        envio = order['shipping']['list_cost'] or 0
        valor_neto = Decimal(str(order['total_amount'] - comision_total - envio))
        order['valor_neto'] = valor_neto
        total_neto_acumulado += float(valor_neto)

        cantidad_items = sum(item['quantity'] for item in order['items'])
        order['cantidad_items'] = cantidad_items
        total_items += cantidad_items

        mejor_info = None
        for item in order['items']:
            isbn = item.get('seller_sku')
            if not isbn or isbn not in stock_data:
                continue
            mejor_info = seleccionar_mejor_proveedor(stock_data[isbn])
            if mejor_info["proveedor"] != "❌":
                break

        if mejor_info and mejor_info["precio"] is not None:
            try:
                precio = float(mejor_info["precio"])
                costo_estimado = round(precio * fleteInternacional * TipoDeCambioMXNEUR, 2)
            except:
                costo_estimado = None
        else:
            costo_estimado = None

        if costo_estimado and costo_estimado > 0:
            costo_decimal = Decimal(str(costo_estimado))
            rentabilidad_mxn = round(valor_neto - costo_decimal, 2)
            rentabilidad_pct = round((rentabilidad_mxn / costo_decimal) * 100, 2)
            total_rentabilidad_mxn += rentabilidad_mxn
            total_costo_estimado += costo_decimal
        else:
            rentabilidad_mxn = None
            rentabilidad_pct = None

        order['stock_info'] = {
            "proveedor": mejor_info["proveedor"] if mejor_info else "❌",
            "stock": mejor_info["stock"] if mejor_info else None,
            "precio": mejor_info["precio"] if mejor_info else None,
            "costo_estimado": costo_estimado,
            "rentabilidad_mxn": rentabilidad_mxn,
            "rentabilidad_pct": rentabilidad_pct
        }

    if total_costo_estimado > 0:
        rentabilidad_promedio_pct = round((total_rentabilidad_mxn / total_costo_estimado) * 100, 2)
    else:
        rentabilidad_promedio_pct = 0

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
        filtro_status=status,
        total_rentabilidad_mxn=total_rentabilidad_mxn,
        rentabilidad_promedio_pct=rentabilidad_promedio_pct,
        total_ventas_mxn=total_ventas_mxn  # 💵 nuevo valor agregado
    )
