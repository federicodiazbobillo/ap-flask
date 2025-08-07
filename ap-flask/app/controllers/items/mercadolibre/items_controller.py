from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import get_conn
import requests

items_mercadolibre_bp = Blueprint(
    'items_mercadolibre_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)


def obtener_gtin(idml, access_token):
    url = f"https://api.mercadolibre.com/items/{idml}?access_token={access_token}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for attr in data.get("attributes", []):
                if attr.get("id") == "GTIN":
                    return attr.get("value_name", "")
        else:
            print(f"⚠️ Error {response.status_code} al consultar item {idml}")
    except Exception as e:
        print(f"❌ Error al consultar GTIN para {idml}: {e}")
    return ""

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
    from app.services.meli_token import get_valid_access_token  # o tu método
    access_token = get_valid_access_token('2025384704')

    cursor = get_conn().cursor()
    cursor.execute("""
        SELECT isbn, seller_sku, items_meli.idml
        FROM items_meli, order_items 
        WHERE 
          CONVERT(items_meli.idml USING utf8mb4) COLLATE utf8mb4_unicode_ci = 
          CONVERT(order_items.item_id USING utf8mb4) COLLATE utf8mb4_unicode_ci
          AND order_items.seller_sku IS NULL
        LIMIT 100
    """)
    columnas = [col[0] for col in cursor.description]
    filas = cursor.fetchall()
    resultados = []

    for fila in filas:
        fila_dict = {col: str(valor or '') for col, valor in zip(columnas, fila)}
        fila_dict["gtin"] = obtener_gtin(fila_dict["idml"], access_token)
        resultados.append(fila_dict)

    cursor.close()
    return render_template("items/mercadolibre/sin_isbn.html", items=resultados)