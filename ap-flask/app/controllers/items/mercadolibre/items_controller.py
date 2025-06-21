from flask import Blueprint, render_template, request,redirect, url_for, flash
from app.db import get_conn
from .check_text import validar_campos_textuales_meli
from app.integrations.openia.image_checker import analizar_imagen_con_ia
from app.integrations.mercadolibre.services.token_service import verificar_meli
import requests

items_meli_bp = Blueprint(
    'items_meli_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)


@items_meli_bp.route('/items/mercadolibre')
def items():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    offset = (page - 1) * limit

    filter_tags = request.args.getlist('tags')
    status = request.args.get("status", None)
    validado = request.args.get("validado")
    

    items = []
    total = 0

    if not filter_tags and not status and validado not in ('0', '1'):
        flash("Aplicá al menos un filtro para buscar ítems.", "info")
        return render_template(
            'items/mercadolibre/items.html',
            items=[],
            total=0,
            page=page,
            limit=limit
        )

    conn = get_conn()
    with conn.cursor() as cursor:
        base_query = """
            SELECT 
                m.idml, m.isbn, m.validado, m.catalog_product_id, 
                m.item_relations, m.catalog_listing, m.catalog_listing_eligible
            FROM items_meli m
            JOIN item_meli_tags t ON t.item_idml = m.idml
        """
        base_where = [
            "m.catalog_listing = 'false'",
            "t.tag = 'catalog_listing_eligible'"
        ]
        query_params = []

        if filter_tags:
            placeholders = ",".join(["%s"] * len(filter_tags))
            base_where.append(f"t.tag IN ({placeholders})")
            query_params.extend(filter_tags)

        if status:
            base_where.append("m.status = %s")
            query_params.append(status)

        if validado in ("0", "1"):
            base_where.append("m.validado = %s")
            query_params.append(int(validado))

        if base_where:
            base_query += " WHERE " + " AND ".join(base_where)

        full_query = f"""
            {base_query}
            GROUP BY m.idml, m.isbn, m.validado, m.catalog_product_id, m.item_relations, m.catalog_listing, m.catalog_listing_eligible
            ORDER BY MAX(m.id) DESC
            LIMIT %s OFFSET %s
        """
        query_params += [limit, offset]
        cursor.execute(full_query, query_params)
        rows = cursor.fetchall()

        # Conteo total
        count_query = """
            SELECT COUNT(DISTINCT m.idml)
            FROM items_meli m
            JOIN item_meli_tags t ON t.item_idml = m.idml
        """
        count_where = [
            "m.catalog_listing = 'false'",
            "t.tag = 'catalog_listing_eligible'"
        ]
        count_params = []

        if filter_tags:
            placeholders = ",".join(["%s"] * len(filter_tags))
            count_where.append(f"t.tag IN ({placeholders})")
            count_params.extend(filter_tags)

        if status:
            count_where.append("m.status = %s")
            count_params.append(status)

        if validado in ("0", "1"):
            count_where.append("m.validado = %s")
            count_params.append(int(validado))

        if count_where:
            count_query += " WHERE " + " AND ".join(count_where)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

    # API de Mercado Libre
    access_token, user_id, error = verificar_meli()
    if error:
        print("❌ Error de token:", error)
        return render_template('items/mercadolibre/items.html', items=[], total=0, page=page, limit=limit)

    for row in rows:
        (
            idml,
            isbn,
            validado,
            catalog_product_id,
            item_relations,
            catalog_listing,
            catalog_listing_eligible
        ) = row

        title, thumbnail, catalog_image = None, None, None

        no_es_catalogable = (
            catalog_product_id is None
            and str(catalog_listing).lower() == 'false'
            and (item_relations is None or item_relations == '')
        )
        catalogable = not no_es_catalogable

        datos_contacto = []
        validado_ia_ahora = False
        try:
            item_url = f"https://api.mercadolibre.com/items/{idml}?access_token={access_token}"
            response = requests.get(item_url, timeout=5)
            if response.ok:
                data = response.json()
                title = data.get("title")
                thumbnail = data.get("thumbnail")
                permalink = data.get("permalink")
                contacto_detectado_textual = validar_campos_textuales_meli(data)
                # Solo analizar imágenes si no está validado
                if validado == 0:
                    pictures = data.get("pictures", [])
                    for pic in pictures:
                        image_url = pic.get("url")
                        if image_url:
                            print(f"🧠 Validando imágenes IA para: {idml}")
                            resultado = analizar_imagen_con_ia(image_url)
                            if resultado.lower().startswith("sí"):
                                datos_contacto.append({"url": image_url, "resultado": resultado})

                    # Si no hay datos de contacto, actualizar validado = 2
                    validado_ia_ahora = False  # valor por defecto
                    if not datos_contacto:
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute(
                                    "UPDATE items_meli SET validado = 2 WHERE idml = %s", (idml,)
                                )
                            conn.commit()
                            validado = 2
                            validado_ia_ahora = True  # ✅ se validó ahora
                        except Exception as e:
                            print(f"⚠️ Error al actualizar validado=2 para {idml}: {e}")

                # Solo consultar /products si es catalogable
                if catalogable and catalog_product_id:
                    catalog_url = f"https://api.mercadolibre.com/products/{catalog_product_id}?access_token={access_token}"
                    cat_resp = requests.get(catalog_url, timeout=5)
                    if cat_resp.ok:
                        cat_data = cat_resp.json()
                        status_catalog = cat_data.get("status")

                        if status_catalog == "active":
                            pictures = cat_data.get("pictures", [])
                            if pictures:
                                catalog_image = pictures[0].get("url")
                        else:
                            children = cat_data.get("children_ids", [])
                            if isinstance(children, list) and len(children) == 1:
                                child_id = children[0]
                                child_url = f"https://api.mercadolibre.com/products/{child_id}?access_token={access_token}"
                                child_resp = requests.get(child_url, timeout=5)
                                if child_resp.ok:
                                    child_data = child_resp.json()
                                    if child_data.get("status") == "active":
                                        catalog_product_id = child_id  # ✅ actualizar
                                        pictures = child_data.get("pictures", [])
                                        if pictures:
                                            catalog_image = pictures[0].get("url")
                                    else:
                                        catalog_image = "varios"  # hijo inactivo
                                else:
                                    catalog_image = "varios"  # error al obtener hijo
                            else:
                                catalog_image = "varios"  # más de un hijo



        except Exception as e:
            print(f"⚠️ Error al consultar {idml}: {e}")
        
        print(f"🔍 [{idml}] contacto_detectado_textual:", contacto_detectado_textual, type(contacto_detectado_textual))

        items.append({
            'idml': idml,
            'isbn': isbn,
            'title': title,
            'thumbnail': thumbnail,
            'catalog_image': catalog_image,
            'validado': validado,
            'permalink' : permalink,
            'catalog_product_id': catalog_product_id,
            'item_relations': item_relations,
            'catalog_listing': catalog_listing,
            'catalog_listing_eligible': catalog_listing_eligible,
            'catalogable': catalogable,
            'datos_contacto': datos_contacto,
            'contacto_detectado_textual': bool(contacto_detectado_textual),
            'validado_ia_ahora': validado_ia_ahora 
        })

    return render_template(
        'items/mercadolibre/items.html',
        items=items,
        total=total,
        page=page,
        limit=limit
    )



@items_meli_bp.route("/catalogar", methods=["POST"])
def catalogar_items():
    seleccionados = request.form.getlist("selected_items")

    if not seleccionados:
        flash("No se seleccionaron productos para catalogar.", "warning")
        return redirect(url_for("items_meli_bp.items"))

    access_token, user_id, error = verificar_meli()
    if error:
        flash(f"Error de token: {error}", "danger")
        return redirect(url_for("items_meli_bp.items"))

    conn = get_conn()
    exitos = 0
    errores = 0

    with conn.cursor() as cursor:
        for idml in seleccionados:
            # Obtener el catalog_product_id desde el formulario
            catalog_product_id = request.form.get(f"catalog_product_id_{idml}")

            if not catalog_product_id:
                print(f"⚠️ Sin catalog_product_id para {idml}")
                errores += 1
                continue

            # Llamar a la API de catalogación
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
                        errores += 1
                        continue

                    # Insertar el nuevo ítem como publicado de catálogo
                    cursor.execute("""
                        INSERT IGNORE INTO items_meli (idml, catalog_product_id, catalog_listing, created_by, validado)
                        VALUES (%s, %s, 'true', 'catalogar_items', 1)
                    """, (nuevo_idml, catalog_product_id))


                    # Actualizar el original con item_relations
                    cursor.execute("""
                        UPDATE items_meli
                        SET item_relations = %s,
                            validado = 1
                        WHERE idml = %s
                    """, (nuevo_idml, idml))

                    exitos += 1
                else:
                    errores += 1
                    print(f"❌ Error catalogando {idml}: {response.status_code} - {response.text}")

            except Exception as e:
                errores += 1
                print(f"⚠️ Excepción catalogando {idml}: {e}")

    conn.commit()
    flash(f"{exitos} ítems catalogados correctamente. {errores} con error.", "info")
    return redirect(url_for("items_meli_bp.items"))
