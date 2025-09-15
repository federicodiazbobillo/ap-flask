from flask import Blueprint, render_template, request, jsonify, redirect, flash
from app.db import get_conn

orders_logistica_bp = Blueprint('orders_logistica', __name__, url_prefix='/orders/logistica')

def _fetch_orders(id_param=None, fecha_desde=None, fecha_hasta=None, 
                  venc_desde=None, venc_hasta=None, nota_like=None, isbn=None):
    """
    Obtiene órdenes con filtros de ID, rango de creación y rango de vencimiento (inclusive),
    agrupa por pack_id (o order_id si pack_id es null) y normaliza datos.
    Además agrega el substatus del envío y el stock de inventario_rayo_ava.
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
    if nota_like:
        filters.append("oi.notas LIKE %s")
        params.append(f"%{nota_like}%")
    if isbn:
        filters.append(
            "EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.order_id AND oi.seller_sku = %s)"
        )
        params.append(isbn)
    
    # Base de consulta incluyendo JOIN con shipments y order_items
    base_query = (
        "SELECT o.order_id, "
        "o.pack_id, "
        "o.created_at, "
        "o.total_amount, "
        "o.status AS order_status, "
        "o.manufacturing_ending_date, "
        "s.status AS shipping_status, "
        "s.substatus AS shipping_substatus "
        "FROM orders o "
        "LEFT JOIN shipments s ON o.shipping_id = s.shipping_id "
        "LEFT JOIN order_items oi ON oi.order_id = o.order_id"
    )

    # Aplicar filtros y orden
    if filters:
        base_query += " WHERE " + " AND ".join(filters)
        base_query += " GROUP BY o.order_id"
        base_query += " ORDER BY o.created_at DESC"
    else:
        base_query += " WHERE DATE(o.created_at) = CURDATE()"

    cursor.execute(base_query, tuple(params) if params else None)
    raw = cursor.fetchall()

    # Agrupar por referencia
    groups = {}
    for row in raw:
        order_id, pack_id, created_at, total_amount, order_status, ending_date, shipping_status, shipping_substatus = row
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
                    'shipping_substatus': shipping_substatus
                },
                'order_ids': []
            }
        groups[reference_id]['order_ids'].append(order_id)

    # Obtener ítems para todas las órdenes agrupadas
    items_map = {}
    skus = set()

    if groups:
        order_ids = [oid for group in groups.values() for oid in group['order_ids']]
        format_ids = ','.join(['%s'] * len(order_ids))
        cursor.execute(
            f"SELECT id, order_id, item_id, seller_sku, quantity, guia, notas "
            f"FROM order_items WHERE order_id IN ({format_ids})",
            tuple(order_ids)
        )
        for row in cursor.fetchall():
            item_db_id, oid, item_id, sku, qty, guia_item, nota_item = row
            items_map.setdefault(oid, []).append({
                'id': item_db_id,
                'item_id': item_id,
                'seller_sku': sku,
                'quantity': qty,
                'guia': guia_item,
                'notas': nota_item
            })
            if sku:
                try:
                    skus.add(int(sku))
                except ValueError:
                    pass  # si no es numérico, lo ignora

    # Consultar inventario_rayo_ava
    stock_map = {}
    if skus:
        format_skus = ','.join(['%s'] * len(skus))
        cursor.execute(
            f"SELECT sku, disponibles, en_inventario, apartados "
            f"FROM inventario_rayo_ava WHERE sku IN ({format_skus})",
            tuple(skus)
        )
        for sku_val, disp, inv, apart in cursor.fetchall():
            stock_map[sku_val] = {
                'disponibles': disp,
                'en_inventario': inv,
                'apartados': apart
            }

    # Construir resultado final
    orders = []
    for group in groups.values():
        meta = group['meta']
        items = []
        for oid in group['order_ids']:
            items.extend(items_map.get(oid, []))
        meta['items'] = items

        # Asignar stock tomando el primer SKU válido de la orden
        if items:
            meta['stock'] = '-'
            for item in items:
                try:
                    sku_int = int(item['seller_sku'])
                    stock = stock_map.get(sku_int)
                    if stock:
                        meta['stock'] = f"{stock['disponibles']}/{stock['en_inventario']}/{stock['apartados']}"
                        break  # usamos el primer SKU con stock encontrado
                except (TypeError, ValueError):
                    continue
        else:
            meta['stock'] = '-'

        orders.append(meta)

    cursor.close()
    return orders



@orders_logistica_bp.route('/')
def index_logistica():
    """
    Vista HTML de logística con filtros por ID, fechas y nota.
    """
    id_param = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    venc_desde = request.args.get('venc_desde')
    venc_hasta = request.args.get('venc_hasta')
    nota_like = request.args.get("nota")
    isbn = request.args.get("isbn")

    orders = _fetch_orders(id_param, fecha_desde, fecha_hasta, venc_desde, venc_hasta, nota_like, isbn)

    return render_template(
        'orders/logistica.html',
        ordenes=orders,
        tipo='logistica',
        filtro_id=id_param,
        filtro_fecha_desde=fecha_desde,
        filtro_fecha_hasta=fecha_hasta,
        filtro_venc_desde=venc_desde,
        filtro_venc_hasta=venc_hasta,
        nota_like=nota_like,
        filtro_isbn=isbn
    )

@orders_logistica_bp.route('/search')
def search_logistica():
    """
    Endpoint JSON para búsqueda de órdenes con filtros.
    """
    id_param = request.args.get('id')
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    venc_desde = request.args.get('venc_desde')
    venc_hasta = request.args.get('venc_hasta')
    nota_like = request.args.get("nota")
    isbn =  request.args.get("isbn")

    orders = _fetch_orders(id_param, fecha_desde, fecha_hasta, venc_desde, venc_hasta, nota_like, isbn)
    return jsonify({'orders': orders})

@orders_logistica_bp.route('/actualizar-nota-item', methods=['POST'])
def actualizar_nota_item():
    """
    Actualiza el campo 'notas' de un item en order_items.
    """
    item_id = request.form.get('item_id')
    nota = request.form.get('notas', '').strip()

    if not item_id:
        flash("ID de item no especificado", "danger")
        return redirect(request.referrer)

    if len(nota) > 20:
        flash("La nota no puede tener más de 20 caracteres", "danger")
        return redirect(request.referrer)

    conn = get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE order_items SET notas = %s WHERE id = %s", (nota, item_id))
        conn.commit()
        print("Actualizando item_id:", item_id, "| nota:", nota)
    except Exception as e:
        conn.rollback()
        print("ERROR Actualizando item_id:", item_id, "| nota:", nota)
    finally:
        cursor.close()

    return redirect(request.referrer)
