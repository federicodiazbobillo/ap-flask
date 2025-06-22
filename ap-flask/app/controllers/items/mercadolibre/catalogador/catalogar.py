from flask import Request, redirect, url_for, flash, session
from app.db import get_conn
import requests

def procesar_catalogacion(req: Request, access_token: str):
    seleccionados = req.form.getlist("selected_items")

    if not seleccionados:
        flash("No se seleccionaron productos para catalogar.", "warning")
        return redirect(url_for("catalogador_bp.items"))

    conn = get_conn()
    exitos = []
    errores = []

    with conn.cursor() as cursor:
        for idml in seleccionados:
            catalog_product_id = req.form.get(f"catalog_product_id_{idml}")

            if not catalog_product_id:
                print(f"⚠️ Sin catalog_product_id para {idml}")
                errores.append(idml)
                continue

            try:
                url = f"https://api.mercadolibre.com/items/catalog_listings?access_token={access_token}"
                payload = {
                    "item_id": idml,
                    "catalog_product_id": catalog_product_id
                }
                response = requests.post(url, json=payload, timeout=5)

                if response.ok:
                    data = response.json()
                    nuevo_idml = data.get("id")

                    if not nuevo_idml:
                        print(f"⚠️ No se obtuvo nuevo ID para {idml}")
                        errores.append(idml)
                        continue

                    cursor.execute("""
                        INSERT IGNORE INTO items_meli (idml, catalog_product_id, catalog_listing, validado)
                        VALUES (%s, %s, 'true', 1)
                    """, (nuevo_idml, catalog_product_id))

                    cursor.execute("""
                        UPDATE items_meli
                        SET item_relations = %s,
                            validado = 1
                        WHERE idml = %s
                    """, (nuevo_idml, idml))

                    exitos.append(idml)
                else:
                    errores.append(idml)
                    print(f"❌ Error catalogando {idml}: {response.status_code} - {response.text}")

            except Exception as e:
                errores.append(idml)
                print(f"⚠️ Excepción catalogando {idml}: {e}")

    conn.commit()

    # Guardar resultados en sesión y redirigir a vista de resultados
    session['catalogacion_resultados'] = {
        'exitos': exitos,
        'errores': errores
    }

    return redirect(url_for("catalogador_bp.resultados"))
