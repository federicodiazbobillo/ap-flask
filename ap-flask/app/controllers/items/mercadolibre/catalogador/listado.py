from flask import Request, request, flash
from app.db import get_conn
from app.integrations.openia.image_checker import analizar_imagen_con_ia
from .check_text import validar_campos_textuales_meli
import requests

def obtener_items(req: Request, access_token: str) -> dict:
    page = int(req.args.get('page', 1))
    limit = int(req.args.get('limit', 50))
    offset = (page - 1) * limit

    filter_tags = req.args.getlist('tags')
    status = req.args.get("status", None)
    validado = req.args.get("validado")

    items = []
    total = 0

    if not filter_tags and not status and validado not in ('0', '1'):
        flash("Aplicá al menos un filtro para buscar ítems.", "info")
        return {
            'items': [], 'total': 0, 'page': page, 'limit': limit
        }

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

    # 🧐 Multi-get para los items
    idmls = [row[0] for row in rows]
    items_meli_api = {}
    if idmls:
        headers = {"Authorization": f"Bearer {access_token}"}
        ids_chunk = [idmls[i:i+20] for i in range(0, len(idmls), 20)]
        for chunk in ids_chunk:
            ids_str = ','.join(chunk)
            multiget_resp = requests.get(
                f"https://api.mercadolibre.com/items?ids={ids_str}",
                headers=headers,
                timeout=10
            )
            if multiget_resp.ok:
                for res in multiget_resp.json():
                    body = res.get("body", {})
                    if body:
                        items_meli_api[body.get("id")] = body

    for row in rows:
        (
            idml, isbn, validado, catalog_product_id,
            item_relations, catalog_listing, catalog_listing_eligible
        ) = row

        title, thumbnail, catalog_image, permalink = None, None, None, None
        no_es_catalogable = (
            catalog_product_id is None and str(catalog_listing).lower() == 'false' and (item_relations is None or item_relations == '')
        )
        catalogable = not no_es_catalogable

        datos_contacto = []
        validado_ia_ahora = False
        contacto_detectado_textual = False
        bloqueado_catalogo = False

        try:
            data = items_meli_api.get(idml)
            if data:
                title = data.get("title")
                thumbnail = data.get("thumbnail")
                permalink = data.get("permalink")
                contacto_detectado_textual = validar_campos_textuales_meli(data)

                # ❌ Verificamos si el tag ya no existe en la API
                tags_api = data.get("tags", [])
                if "catalog_listing_eligible" not in tags_api and isinstance(data.get("item_relations"), list) and data["item_relations"]:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "DELETE FROM item_meli_tags WHERE item_idml = %s AND tag = 'catalog_listing_eligible'",
                                (idml,)
                            )
                        conn.commit()
                        catalogable = False
                    except Exception as e:
                        print(f"⚠️ Error al eliminar tag catalog_listing_eligible para {idml}: {e}")

                if validado == 0:
                    pictures = data.get("pictures", [])
                    for pic in pictures:
                        url = pic.get("url")
                        if url:
                            resultado = analizar_imagen_con_ia(url)
                            if resultado.lower().startswith("sí"):
                                datos_contacto.append({"url": url, "resultado": resultado})

                    if not datos_contacto:
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute("UPDATE items_meli SET validado = 2 WHERE idml = %s", (idml,))
                            conn.commit()
                            validado = 2
                            validado_ia_ahora = True
                        except Exception as e:
                            print(f"⚠️ Error al actualizar validado=2 para {idml}: {e}")

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
                            hijos_activos = []

                            for child_id in children:
                                child_url = f"https://api.mercadolibre.com/products/{child_id}?access_token={access_token}"
                                child_resp = requests.get(child_url, timeout=5)
                                if child_resp.ok:
                                    child_data = child_resp.json()
                                    if child_data.get("status") == "active":
                                        hijos_activos.append(child_id)

                            if len(hijos_activos) == 1:
                                catalog_product_id = hijos_activos[0]
                                child_url = f"https://api.mercadolibre.com/products/{catalog_product_id}?access_token={access_token}"
                                child_resp = requests.get(child_url, timeout=5)
                                if child_resp.ok:
                                    pictures = child_resp.json().get("pictures", [])
                                    if pictures:
                                        catalog_image = pictures[0].get("url")
                            else:
                                catalog_image = "varios"
                                bloqueado_catalogo = True
                    else:
                        bloqueado_catalogo = True

        except Exception as e:
            print(f"⚠️ Error al consultar {idml}: {e}")

        items.append({
            'idml': idml,
            'isbn': isbn,
            'title': title,
            'thumbnail': thumbnail,
            'catalog_image': catalog_image,
            'validado': validado,
            'permalink': permalink,
            'catalog_product_id': catalog_product_id,
            'item_relations': item_relations,
            'catalog_listing': catalog_listing,
            'catalog_listing_eligible': catalog_listing_eligible,
            'catalogable': catalogable,
            'datos_contacto': datos_contacto,
            'contacto_detectado_textual': bool(contacto_detectado_textual),
            'validado_ia_ahora': validado_ia_ahora,
            'bloqueado_catalogo': bloqueado_catalogo
        })

    return {
        'items': items,
        'total': total,
        'page': page,
        'limit': limit
    }
