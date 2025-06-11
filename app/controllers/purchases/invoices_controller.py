from flask import Blueprint, render_template

# Blueprint with English-named route and endpoint
invoices_bp = Blueprint('invoices_suppliers', __name__, url_prefix='/purchases/invoices_suppliers')

@invoices_bp.route('/')
def index():
    return render_template('purchases/invoices_suppliers.html', tipo='suppliers')


import pandas as pd
from flask import request, redirect, flash
from app.db import get_conn

@invoices_bp.route('/upload_celesa', methods=['POST'])
def upload():
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash("Invalid file format. Please upload a .csv file.", "danger")
        return redirect(request.referrer)

    # Leer CSV
    df = pd.read_csv(file, sep=";", encoding="latin1")

    required_cols = ['NUM_DOCUMENTO', 'FECHA', 'EAN', 'IMPORTE', 'UNIDADES']
    if not all(col in df.columns for col in required_cols):
        flash("CSV file missing required columns.", "danger")
        return redirect(request.referrer)

    # Preprocesamiento
    df = df[required_cols].copy()
    df.columns = ['nro_fc', 'fecha', 'isbn', 'importe', 'unidades']
    df['isbn'] = df['isbn'].astype(str).str.strip()
    df['importe'] = df['importe'].str.replace(",", ".").astype(float)
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True).dt.date
    df['unidades'] = pd.to_numeric(df['unidades'], errors='coerce').fillna(1).astype(int)
    df['proveedor'] = 'Celesa'
    df['order_id'] = None

    # Repetir cada fila según "unidades"
    df_expanded = df.loc[df.index.repeat(df['unidades'])].drop(columns=['unidades'])

    # Insertar en DB
    conn = get_conn()
    cursor = conn.cursor()

    for _, row in df_expanded.iterrows():
        cursor.execute("""
            INSERT INTO facturas_proveedores (proveedor, nro_fc, fecha, isbn, importe, order_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (row.proveedor, row.nro_fc, row.fecha, row.isbn, row.importe, row.order_id))

    conn.commit()
    cursor.close()

    flash(f"{len(df_expanded)} invoice rows loaded successfully.", "success")
    return redirect(request.referrer)
