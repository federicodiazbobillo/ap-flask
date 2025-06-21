from flask import Blueprint, render_template, request,redirect, url_for, flash
from app.db import get_conn
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
    catalogable_filter = request.args.get("catalogable")

    items = []
    total = 0

    if not filter_tags and not status and validado not in ('0', '1') and catalogable_filter not in ('0', '1'):
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
        base_where = ["m.catalog_listing = 'false'"]
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

        if catalogable_filter == '1':
            base_where.append("""
                NOT (
                    m.catalog_product_id IS NULL 
                    AND m.catalog_listing = 'false' 
                    AND (m.item_relations IS NULL OR m.item_relations = '')
                )
            """)
        elif catalogable_filter == '0':
            base_where.append("""
                m.catalog_product_id IS NULL 
                AND m.catalog_listing = 'false' 
                AND (m.item_relations IS NULL OR m.item_relations = '')
            """)

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
        count_where = ["m.catalog_listing = 'false'"]
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

        if catalogable_filter == '1':
            count_where.append("""
                NOT (
                    m.catalog_product_id IS NULL 
                    AND m.catalog_listing = 'false' 
                    AND (m.item_relations IS NULL OR m.item_relations = '')
                )
            """)
        elif catalogable_filter == '0':
            count_where.append("""
                m.catalog_product_id IS NULL 
                AND m.catalog_listing = 'false' 
                AND (m.item_relations IS NULL OR m.item_relations = '')
            """)

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

        try:
            item_url = f"https://api.mercadolibre.com/items/{idml}?access_token={access_token}"
            response = requests.get(item_url, timeout=5)
            if response.ok:
                data = response.json()
                title = data.get("title")
                thumbnail = data.get("thumbnail")

                # Solo consultar /products si es catalogable
                if catalogable and catalog_product_id:
                    catalog_url = f"https://api.mercadolibre.com/products/{catalog_product_id}?access_token={access_token}"
                    cat_resp = requests.get(catalog_url, timeout=5)
                    if cat_resp.ok:
                        cat_data = cat_resp.json()
                        pictures = cat_data.get("pictures", [])
                        if pictures:
                            catalog_image = pictures[0].get("url")
        except Exception as e:
            print(f"⚠️ Error al consultar {idml}: {e}")

        items.append({
            'idml': idml,
            'isbn': isbn,
            'title': title,
            'thumbnail': thumbnail,
            'catalog_image': catalog_image,
            'validado': validado,
            'catalog_product_id': catalog_product_id,
            'item_relations': item_relations,
            'catalog_listing': catalog_listing,
            'catalog_listing_eligible': catalog_listing_eligible,
            'catalogable': catalogable
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
