from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import get_conn

items_mercadolibre_bp = Blueprint(
    'items_mercadolibre_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@items_mercadolibre_bp.route('/asignar_isbn', methods=['POST'])
def asignar_isbn():
    idml = request.form.get('idml')
    nuevo_isbn = request.form.get('isbn')

    if not idml or not nuevo_isbn:
        flash("Faltan datos para guardar ISBN", "danger")
        return redirect(url_for('items_mercadolibre_bp.items_sin_isbn'))

    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE order_items 
            SET seller_sku = %s 
            WHERE item_id = %s
        """, (nuevo_isbn, idml))
        conn.commit()
        cursor.close()
        flash(f"✅ ISBN asignado a {idml}", "success")
    except Exception as e:
        print("❌ Error al asignar ISBN:", e)
        flash("Error al guardar el ISBN", "danger")

    return redirect(url_for('items_mercadolibre_bp.items_sin_isbn'))

@items_mercadolibre_bp.route('/sin_isbn')
def items_sin_isbn():
    try:
        cursor = get_conn().cursor()
        cursor.execute("""
            SELECT isbn, seller_sku, items_meli.idml
            FROM items_meli, order_items 
            WHERE 
              CONVERT(items_meli.idml USING utf8mb4) COLLATE utf8mb4_unicode_ci = 
              CONVERT(order_items.item_id USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND order_items.seller_sku IS NULL
            LIMIT 200
        """)
        columnas = [col[0] for col in cursor.description]
        filas = cursor.fetchall()
        resultados = [
            {col: str(valor or '') for col, valor in zip(columnas, fila)}
            for fila in filas
        ]
        cursor.close()  # ✔️ Sí se cierra el cursor
    except Exception as e:
        print("❌ ERROR en sin_isbn:", e)
        resultados = []
    return render_template("items/mercadolibre/sin_isbn.html", items=resultados)