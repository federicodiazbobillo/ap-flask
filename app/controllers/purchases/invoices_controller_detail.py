# app/controllers/purchases/invoices_controller_detail.py
from flask import Blueprint, render_template, request
from app.db import get_conn

invoices_detail_bp = Blueprint('invoices_suppliers_detail', __name__, url_prefix='/purchases/invoices_suppliers/detail')

@invoices_detail_bp.route('/<nro_fc>')
def view(nro_fc):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fecha, proveedor, isbn, importe, order_id, tipo_factura
        FROM invoices_suppliers
        WHERE nro_fc = %s
    """, (nro_fc,))
    items = cursor.fetchall()
    cursor.close()

    return render_template(
        'purchases/invoices_suppliers_detail.html',
        nro_fc=nro_fc,
        items=items
    )
