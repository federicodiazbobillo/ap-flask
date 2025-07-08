from flask import Blueprint, render_template
from app.db import get_conn

compras_revision_bp = Blueprint('compras_revision', __name__, url_prefix='/purchases/compras_revision')


@compras_revision_bp.route('/')
def index():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT proveedor, nro_fc, fecha, isbn, importe, guia
        FROM invoices_suppliers
        WHERE order_id = 9999999999
        ORDER BY fecha DESC
    """)
    compras = [
        {
            'proveedor': row[0],
            'nro_fc': row[1],
            'fecha': row[2],
            'isbn': row[3],
            'importe': row[4],
            'guia': row[5],
        }
        for row in cursor.fetchall()
    ]

    cursor.close()
    return render_template('purchases/compras_revision.html', compras=compras)
