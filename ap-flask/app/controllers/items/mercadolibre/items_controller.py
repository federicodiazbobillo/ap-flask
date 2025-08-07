from flask import Blueprint, render_template
from app.db import get_conn

items_mercadolibre_bp = Blueprint(
    'items_mercadolibre_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

def limpiar(texto):
    if texto is None:
        return ''
    return str(texto).encode('utf-8', 'ignore').decode('utf-8')

@items_mercadolibre_bp.route('/sin_isbn')
def items_sin_isbn():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT isbn, seller_sku, items_meli.idml
        FROM items_meli, order_items 
        WHERE 
          CONVERT(items_meli.idml USING utf8mb4) COLLATE utf8mb4_unicode_ci = 
          CONVERT(order_items.item_id USING utf8mb4) COLLATE utf8mb4_unicode_ci
          AND order_items.seller_sku IS NULL
        LIMIT 200
    """)
    filas = cursor.fetchall()
    columnas = [col[0] for col in cursor.description]

    resultados = [
        {col: limpiar(valor) for col, valor in zip(columnas, fila)}
        for fila in filas
    ]

    cursor.close()
    conn.close()
    return render_template("items/mercadolibre/sin_isbn.html", items=resultados)
