from flask import Blueprint, render_template, request, redirect, jsonify
from app.db import get_conn
from app.utils.order_status import estado_logico

invoices_detail_bp = Blueprint('invoices_suppliers_detail', __name__, url_prefix='/purchases/invoices_suppliers/detail')

@invoices_detail_bp.route('/<nro_fc>')
def view(nro_fc):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            isup.id,
            isup.fecha,
            isup.proveedor,
            isup.isbn,
            isup.importe,
            isup.order_id,
            isup.tipo_factura,
            isup.tc,
            CASE WHEN ira.sku IS NULL THEN 0 ELSE 1 END AS en_rayo
        FROM invoices_suppliers isup
        LEFT JOIN inventario_rayo_ava ira
            ON isup.isbn REGEXP '^[0-9]+$' AND ira.sku = CAST(isup.isbn AS UNSIGNED)
        WHERE isup.nro_fc = %s
    """, (nro_fc,))
    items = cursor.fetchall()
    tc = items[0][7] if items else None
    cursor.close()
    return render_template('purchases/invoices_suppliers_detail.html', nro_fc=nro_fc, items=items, tc=tc)

@invoices_detail_bp.route('/buscar_ordenes_por_isbn', methods=['POST'])
def buscar_ordenes_por_isbn():
    isbn = request.json.get('isbn')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            o.order_id,
            o.created_at,
            o.total_amount,
            o.status,
            s.status AS shipment_status,
            s.substatus,
            oi.id AS order_item_id,
            oi.quantity,
            COALESCE(COUNT(isup.id), 0) AS unidades_vinculadas
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        LEFT JOIN invoices_suppliers isup 
            ON isup.order_id = o.order_id AND isup.isbn = oi.seller_sku
        WHERE oi.seller_sku = %s
        GROUP BY o.order_id, oi.id
        ORDER BY o.created_at DESC
    """, (isbn,))
    rows = cursor.fetchall()
    cursor.close()

    ordenes = []
    for row in rows:
        estado = estado_logico(row[3], row[4], row[5])
        ordenes.append({
            "order_id": row[0],
            "fecha": row[1].strftime('%d-%m-%Y') if row[1] else None,
            "total": row[2],
            "estado": estado,
            "order_item_id": row[6],
            "quantity": row[7],
            "vinculadas": row[8],
        })

    return jsonify(ordenes)

@invoices_detail_bp.route('/vincular_orden', methods=['POST'])
def vincular_orden():
    item_id = request.form.get('item_id')
    order_id = request.form.get('order_id')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET order_id = %s
        WHERE id = %s
    """, (order_id, item_id))
    conn.commit()
    cursor.close()
    return redirect(request.referrer)

@invoices_detail_bp.route('/desvincular_orden', methods=['POST'])
def desvincular_orden():
    item_id = request.form.get('item_id')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET order_id = NULL
        WHERE id = %s
    """, (item_id,))
    conn.commit()
    cursor.close()
    return redirect(request.referrer)

@invoices_detail_bp.route('/actualizar_tc_factura', methods=['POST'])
def actualizar_tc_factura():
    nro_fc = request.form.get('nro_fc')
    tc = request.form.get('tc')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET tc = %s
        WHERE nro_fc = %s
    """, (tc, nro_fc))
    conn.commit()
    cursor.close()
    return redirect(request.referrer)
