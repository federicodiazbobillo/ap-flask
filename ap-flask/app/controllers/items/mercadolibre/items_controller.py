from flask import Blueprint, render_template, request, redirect, url_for, flash, session

@items_mercadolibre_bp.route('/sin_isbn')
def items_sin_isbn():
    conn = get_app_connection()
    with conn.cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT isbn, seller_sku, items_meli.idml
            FROM items_meli, order_items 
            WHERE 
              CONVERT(items_meli.idml USING utf8mb4) COLLATE utf8mb4_unicode_ci = 
              CONVERT(order_items.item_id USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND order_items.seller_sku IS NULL
        """)
        resultados = cursor.fetchall()
    conn.close()
    return render_template("items/mercadolibre/sin_isbn.html", items=resultados)
