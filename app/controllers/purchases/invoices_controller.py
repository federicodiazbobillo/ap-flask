from flask import Blueprint, render_template

# Blueprint with English-named route and endpoint
invoices_bp = Blueprint('invoices_suppliers', __name__, url_prefix='/purchases/invoices_suppliers')

@invoices_bp.route('/')
def index():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            nro_fc,
            fecha,
            proveedor,
            COUNT(*) AS total,
            SUM(CASE WHEN order_id IS NOT NULL THEN 1 ELSE 0 END) AS sincronizados,
            SUM(importe) AS total_importe,
            tipo_factura,
            MIN(id) AS ejemplo_id
        FROM invoices_suppliers
        GROUP BY nro_fc, fecha, proveedor, tipo_factura
        ORDER BY fecha DESC, nro_fc

    """)
    facturas = cursor.fetchall()
    cursor.close()

    return render_template(
        'purchases/invoices_suppliers.html',
        tipo='suppliers',
        facturas=facturas
    )


import pandas as pd
from flask import request, redirect, flash
from app.db import get_conn

@invoices_bp.route('/upload_celesa', methods=['POST'])
def upload_celesa():
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash("Invalid file format. Please upload a .csv file.", "danger")
        return redirect(request.referrer)

    # Leer CSV
    try:
        df = pd.read_csv(file, sep=";", encoding="latin1")
    except Exception as e:
        flash(f"Failed to read CSV: {e}", "danger")
        return redirect(request.referrer)

    # Validar columnas requeridas
    required_cols = ['NUM_DOCUMENTO', 'FECHA', 'EAN', 'IMPORTE', 'UNIDADES']
    if not all(col in df.columns for col in required_cols):
        flash("CSV file missing required columns.", "danger")
        return redirect(request.referrer)

    # Preprocesamiento
    df = df[required_cols].copy()
    df.columns = ['nro_fc', 'fecha', 'isbn', 'importe', 'unidades']
    df['isbn'] = df['isbn'].astype(str).str.strip()
    df['importe'] = df['importe'].str.replace(",", ".").astype(float)
    df['unidades'] = pd.to_numeric(df['unidades'], errors='coerce').fillna(1).astype(int)
    df['importe'] = df['importe'] / df['unidades']  # ✅ dividir después de convertir
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True).dt.date
    df['proveedor'] = 'Celesa'
    df['order_id'] = None


    # Verificar facturas duplicadas por nro_fc
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nro_fc FROM invoices_suppliers WHERE nro_fc IN %s",
        (tuple(df['nro_fc'].unique()),)
    )
    existing = set(row[0] for row in cursor.fetchall())

    if existing:
        flash(f"These invoice numbers already exist and cannot be uploaded again: {', '.join(existing)}", "danger")
        cursor.close()
        return redirect(request.referrer)

    # Expandir filas según cantidad de unidades
    df_expanded = df.loc[df.index.repeat(df['unidades'])].drop(columns=['unidades'])

    # Insertar registros
    for _, row in df_expanded.iterrows():
        cursor.execute("""
            INSERT INTO invoices_suppliers (proveedor, nro_fc, fecha, isbn, importe, order_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (row.proveedor, row.nro_fc, row.fecha, row.isbn, row.importe, row.order_id))

    conn.commit()
    cursor.close()

    flash(f"{len(df_expanded)} invoice rows loaded successfully.", "success")
    return redirect(request.referrer)


@invoices_bp.route('/cambiar_tipo_factura', methods=['POST'])
def cambiar_tipo_factura():
    item_id = request.form.get('item_id')
    nuevo_tipo = request.form.get('nuevo_tipo')
    if nuevo_tipo not in ['mercaderia', 'envio']:
        flash("Tipo de factura inválido", "danger")
        return redirect(request.referrer)

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices_suppliers
        SET tipo_factura = %s
        WHERE id = %s
    """, (nuevo_tipo, item_id))
    conn.commit()
    cursor.close()
    flash(f"Tipo de factura actualizado a '{nuevo_tipo}'", "success")
    return redirect(request.referrer)