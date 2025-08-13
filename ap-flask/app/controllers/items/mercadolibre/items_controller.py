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

    conn = get_conn()
    cursor = conn.cursor()
    try:
        # Trae datos base: idml, isbn (DB) y seller_sku (debería venir NULL por el filtro)
        cursor.execute("""
            SELECT 
                im.isbn        AS isbn,
                oi.seller_sku  AS seller_sku,
                im.idml        AS idml
            FROM items_meli im
            JOIN order_items oi
              ON CONVERT(im.idml USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                 CONVERT(oi.item_id USING utf8mb4) COLLATE utf8mb4_unicode_ci
            WHERE oi.seller_sku IS NULL
            LIMIT 100
        """)
        columnas = [col[0] for col in cursor.description]
        filas = cursor.fetchall()
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        # Si usás flask_mysqldb, no cierres aquí conn; lo hace el teardown.

    # Normalizamos filas a dicts de strings (evita None en el template)
    registros = [
        {col: ('' if val is None else str(val)) for col, val in zip(columnas, fila)}
        for fila in filas
    ]

    BATCH_SIZE = 20
    resultados = []

    # Procesamos en lotes para pedir GTINs a ML
    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i + BATCH_SIZE]
        idmls = [r['idml'] for r in batch if r.get('idml')]

        gtins = obtener_gtins_batch(idmls, access_token) if idmls else {}  # {idml: gtin}

        for r in batch:
            idml = r.get('idml', '')
            gtin_ml = gtins.get(idml, '')

            # Sugerencia para "Nuevo ISBN": GTIN si existe, si no el ISBN de la DB
            sugerido = gtin_ml or r.get('isbn', '')

            resultados.append({
                'idml': idml,
                'isbn': r.get('isbn', ''),           # ISBN en BD (items_meli.isbn)
                'seller_sku': r.get('seller_sku',''),# No lo mostramos en este módulo, pero lo dejamos por si se usa luego
                'gtin': sugerido                      # Valor sugerido para el input "Nuevo ISBN"
            })

    return render_template("items/mercadolibre/sin_isbn.html", items=resultados)


@items_mercadolibre_bp.route('/asignar_isbn_bulk', methods=['POST'])
def asignar_isbn_bulk():
    # IDs seleccionados (tildados)
    seleccionados = request.form.getlist('sel[]')          # lista de idml
    # ISBNs por idml (vienen con clave tipo isbn[<idml>])
    # En request.form las claves son literales, ejemplo: "isbn[MLM123]"
    # Vamos a leer por cada idml seleccionado su ISBN correspondiente
    if not seleccionados:
        flash("No hay ítems seleccionados.", "warning")
        return redirect(url_for('items_mercadolibre_bp.items_sin_isbn'))

    conn = get_conn()
    cursor = conn.cursor()
    ok, skipped, errors = 0, 0, 0

    for idml in seleccionados:
        isbn_val = request.form.get(f'isbn[{idml}]', '').strip()
        if not isbn_val:
            skipped += 1
            continue
        try:
            cursor.execute("""
                UPDATE order_items
                SET seller_sku = %s
                WHERE CONVERT(item_id USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                      CONVERT(%s USING utf8mb4) COLLATE utf8mb4_unicode_ci
            """, (isbn_val, idml))
            ok += cursor.rowcount
        except Exception as e:
            errors += 1
            print(f"❌ Error al asignar ISBN para {idml}: {e}")

    try:
        conn.commit()
    finally:
        cursor.close()
        # Si usás flask_mysqldb, podés dejar que el teardown cierre la conexión.

    msg = f"✅ Actualizados: {ok}"
    if skipped:
        msg += f" | ⏭️ Omitidos (sin ISBN): {skipped}"
    if errors:
        msg += f" | ❌ Errores: {errors}"
    flash(msg, "info")

    return redirect(url_for('items_mercadolibre_bp.items_sin_isbn'))


