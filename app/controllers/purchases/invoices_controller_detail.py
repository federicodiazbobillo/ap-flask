from flask import Blueprint, render_template, request, redirect, flash, jsonify
from app.db import get_conn

invoices_detail_bp = Blueprint('invoices_suppliers_detail', __name__, url_prefix='/purchases/invoices_suppliers/detail')

@invoices_detail_bp.route('/<nro_fc>')
def view(nro_fc):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fecha, proveedor, isbn, importe, order_id, tipo_factura
        FROM invoices_suppliers
        WHERE nro_fc = %s
    """, (nro_fc,))
    items = cursor.fetchall()
    cursor.close()
    return render_template('purchases/invoices_suppliers_detail.html', nro_fc=nro_fc, items=items)

@invoices_detail_bp.route('/buscar_ordenes_por_isbn', methods=['POST'])
def buscar_ordenes_por_isbn():
    isbn = request.json.get('isbn')
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT 
            o.order_id,
            o.created_at,
            o.total_amount,
            o.status,
            s.status AS shipment_status,
            s.substatus
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        LEFT JOIN shipments s ON o.shipping_id = s.shipping_id
        WHERE oi.seller_sku = %s
        ORDER BY o.created_at DESC
    """, (isbn,))
    rows = cursor.fetchall()
    cursor.close()

    ordenes = []
    for row in rows:
        ordenes.append([
            row[0],  # order_id
            row[1].strftime('%d-%m-%Y') if row[1] else None,
            row[2],  # total_amount
            row[3],  # order.status
            row[4],  # shipment.status
            row[5],  # shipment.substatus
        ])

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
    flash("Orden vinculada exitosamente", "success")
    return redirect(request.referrer)
