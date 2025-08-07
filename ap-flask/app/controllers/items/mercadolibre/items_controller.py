from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db import get_conn
from app.integrations.mercadolibre.services.token_service import verificar_meli
import requests

items_mercadolibre_bp = Blueprint(
    'items_mercadolibre_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)


def obtener_gtins_batch(idml_list, access_token):
    url = "https://api.mercadolibre.com/items"
    params = {
        "ids": ",".join(idml_list),
        "access_token": access_token
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            gtins = {}
            for item in response.json():
                body = item.get("body", {})
                idml = body.get("id")
                gtin = ""
                for attr in body.get("attributes", []):
                    if attr.get("id") == "GTIN":
                        gtin = attr.get("value_name", "")
                        break
                gtins[idml] = gtin
            return gtins
        else:
            print(f"⚠️ Error {response.status_code} al consultar multiget:", response.text)
    except Exception as e:
        print(f"❌ Error en multiget: {e}")
    return {}


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
    access_token, user_id, error = verificar_meli()

    if not access_token:
        flash("No se pudo obtener el token de Mercado Libre", "danger")
        return redirect(url_for('home.index'))

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
    cursor.close()

    BATCH_SIZE = 20
    resultados = []

    for i in range(0, len(filas), BATCH_SIZE):
        batch = filas[i:i + BATCH_SIZE]
        idmls = [str(f[2]) for f in batch]  # idml está en la columna 3
        gtins = obtener_gtins_batch(idmls, access_token)

        for fila in batch:
            fila_dict = {col: str(valor or '') for col, valor in zip(columnas, fila)}
            fila_dict["gtin"] = gtins.get(fila_dict["idml"], "")
            resultados.append(fila_dict)

    return render_template("items/mercadolibre/sin_isbn.html", items=resultados)
