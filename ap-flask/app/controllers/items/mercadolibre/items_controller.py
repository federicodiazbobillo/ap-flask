from flask import Blueprint, render_template, request
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

    items = []
    total = 0

    if filter_tags:
        placeholders = ",".join(["%s"] * len(filter_tags))
        having_count = len(filter_tags)

        conn = get_conn()
        with conn.cursor() as cursor:
            query = f"""
                SELECT m.idml, m.isbn
                FROM items_meli m
                JOIN item_meli_tags t ON t.item_idml = m.idml
                WHERE t.tag IN ({placeholders})
                GROUP BY m.idml, m.isbn
                HAVING COUNT(DISTINCT t.tag) = %s
                ORDER BY m.id DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, (*filter_tags, having_count, limit, offset))
            rows = cursor.fetchall()

            count_query = f"""
                SELECT COUNT(*) FROM (
                    SELECT 1
                    FROM items_meli m
                    JOIN item_meli_tags t ON t.item_idml = m.idml
                    WHERE t.tag IN ({placeholders})
                    GROUP BY m.idml, m.isbn
                    HAVING COUNT(DISTINCT t.tag) = %s
                ) AS sub
            """
            cursor.execute(count_query, (*filter_tags, having_count))
            total = cursor.fetchone()[0]

        access_token, user_id, error = verificar_meli()
        if error:
            print("❌ Error de token:", error)
            return render_template('items/mercadolibre/items.html', items=[], total=0, page=page, limit=limit)

        for row in rows:
            idml, isbn = row[0], row[1]
            title, thumbnail, catalog_product_id, catalog_image = None, None, None, None

            try:
                item_url = f"https://api.mercadolibre.com/items/{idml}?access_token={access_token}"
                response = requests.get(item_url, timeout=5)
                if response.ok:
                    data = response.json()
                    title = data.get("title")
                    thumbnail = data.get("thumbnail")
                    catalog_product_id = data.get("catalog_product_id")

                    if catalog_product_id:
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
                'catalog_image': catalog_image
            })

    return render_template(
        'items/mercadolibre/items.html',
        items=items,
        total=total,
        page=page,
        limit=limit
    )
