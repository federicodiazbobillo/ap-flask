# app/controllers/orders/orders_costos_controller.py
from decimal import Decimal, ROUND_HALF_UP
from flask import Blueprint, render_template, request
from app.db import get_conn
from app.integrations.apimongo.stock import obtener_stock_por_lote, seleccionar_mejor_proveedor
from datetime import date

# 💱 Variables de conversión (pueden venir luego de un config o API)
TipoDeCambioMXNEUR = Decimal('22')
fleteInternacional = Decimal('1.25')

orders_costos_bp = Blueprint('orders_costos', __name__, url_prefix='/orders/costos')

@orders_costos_bp.route('/')
def index_costos():
    conn = get_conn()
    cursor = conn.cursor()

    # 🔎 Filtros GET
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    status = request.args.get('status')

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

    if not filters:
        where_clause = "WHERE DATE(o.created_at) = CURDATE()"
        fecha_desde = fecha_hasta = date.today().isoformat()
    else:
        where_clause = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT o.order_id, o.created_at, o.total_amount, o.status, o.shipping_id, s.list_cost
        FROM orders o
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        {where_clause}
        ORDER BY o.created_at DESC
    """

    cursor.execute(query, tuple(params))
    raw_orders = cursor.fetchall()

    orders = []
    order_ids = []
    total_ventas_mxn = 0

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
        total_ventas_mxn += row[2] or 0

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
                'order_id': r[0],
                'item_id': r[1],
                'seller_sku': r[2],
                'quantity': r[3],
                'manufacturing_days': r[4],
                'sale_fee': r[5],
            }
            items_map.setdefault(r[0], []).append(item)

    total_neto_acumulado = 0
    total_items = 0
    total_ordenes = len(orders)
    total_rentabilidad_mxn = Decimal('0.00')
    total_costo_estimado = Decimal('0.00')

    all_isbns = {item['seller_sku'] for order in orders for item in items_map.get(order['order_id'], []) if item['seller_sku']}
    stock_data = obtener_stock_por_lote(list(all_isbns))

    for order in orders:
        order['items'] = items_map.get(order['order_id'], [])

        comision_total = sum(Decimal(item['sale_fee']) * item['quantity'] for item in order['items'])
        envio = Decimal(order['shipping']['list_cost'] or 0)
        cantidad_items = sum(item['quantity'] for item in order['items'])
        order['cantidad_items'] = cantidad_items

        costo_estimado = Decimal('0.00')
        mejor_info = None

        for item in order['items']:
            isbn = item.get('seller_sku')
            cantidad = item.get('quantity', 0)

            if not isbn or isbn not in stock_data:
                continue

            info = seleccionar_mejor_proveedor(stock_data[isbn])
            if info["proveedor"] == "❌" or info["precio"] is None:
                continue

            if mejor_info is None:
                mejor_info = info

            try:
                precio_unitario = Decimal(str(info["precio"]))
                costo_item_total = precio_unitario * fleteInternacional * TipoDeCambioMXNEUR * cantidad
                costo_estimado += costo_item_total
            except Exception:
                continue

        if costo_estimado > 0:
            costo_estimado = costo_estimado.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            valor_neto = Decimal(order['total_amount']) - comision_total - envio
            impuesto = Decimal(order['total_amount']) * Decimal('0.025')
            costos_operativos = Decimal('20.00') * cantidad_items
            rentabilidad_neta_mxn = valor_neto - costo_estimado - impuesto - costos_operativos
            rentabilidad_neta_mxn = rentabilidad_neta_mxn.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            rentabilidad_neta_pct = (rentabilidad_neta_mxn / costo_estimado * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            order['valor_neto'] = valor_neto
            order['stock_info'] = {
                "proveedor": mejor_info["proveedor"] if mejor_info else "❌",
                "stock": mejor_info["stock"] if mejor_info else None,
                "precio": mejor_info["precio"] if mejor_info else None,
                "costo_estimado": costo_estimado,
                "rentabilidad_mxn": rentabilidad_neta_mxn,
                "rentabilidad_pct": rentabilidad_neta_pct
            }

            # 🔢 Solo acumular si hubo proveedor
            total_neto_acumulado += float(valor_neto)
            total_items += cantidad_items
            total_rentabilidad_mxn += rentabilidad_neta_mxn
            total_costo_estimado += costo_estimado
        else:
            order['valor_neto'] = None
            order['stock_info'] = {
                "proveedor": "❌",
                "stock": None,
                "precio": None,
                "costo_estimado": None,
                "rentabilidad_mxn": None,
                "rentabilidad_pct": None
            }



    rentabilidad_promedio_pct = (
        (total_rentabilidad_mxn / total_costo_estimado * 100).quantize(Decimal("0.01"))
        if total_costo_estimado > 0 else 0
    )

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
        total_ventas_mxn=total_ventas_mxn
    )
