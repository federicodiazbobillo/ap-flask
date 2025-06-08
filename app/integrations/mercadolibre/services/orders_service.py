import requests
from app.db import get_conn
from .shipments_service import guardar_envios

def obtener_ordenes(access_token, user_id, date_from=None, date_to=None):
    url = "https://api.mercadolibre.com/orders/search"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    ordenes = []
    offset = 0
    limit = 50

    while True:
        params = {
            "seller": user_id,
            "limit": limit,
            "offset": offset,
            "sort": "date_desc"
        }

        # Si se pasa un rango de fechas, lo agregamos a los params
        if date_from:
            params["order.date_created.from"] = date_from
        if date_to:
            params["order.date_created.to"] = date_to

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return {
                "error": True,
                "message": f"HTTP {response.status_code}: {response.text}"
            }

        data = response.json()
        batch = data.get("results", [])
        if not batch:
            break

        ordenes.extend(batch)
        offset += len(batch)

    # ✅ Aquí agregamos el user_id correctamente
    guardar_ordenes_en_db(ordenes, user_meli_id=user_id)

    # recolectar shipping_ids de todas las órdenes
    shipping_ids = [orden.get("shipping", {}).get("id") for orden in ordenes if orden.get("shipping")]

    # guardar envíos
    guardar_envios(shipping_ids, access_token)
    
    return {
        "error": False,
        "ordenes": ordenes
    }




def guardar_ordenes_en_db(ordenes, user_meli_id=None):
    conn = get_conn()
    cursor = conn.cursor()

    for orden in ordenes:
        order_id = orden.get("id")
        created_at = orden.get("date_created")
        last_updated = orden.get("last_updated")
        pack_id = orden.get("pack_id")
        total_amount = orden.get("total_amount")
        status = orden.get("status")
        manufacturing_ending_date = orden.get("manufacturing_ending_date")
        shipping_id = orden.get("shipping", {}).get("id")

        if not order_id or not created_at:
            continue

        cursor.execute("""
            INSERT INTO orders (
                order_id, created_at, last_updated, pack_id,
                total_amount, status, manufacturing_ending_date, shipping_id, user_meli_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_updated = VALUES(last_updated),
                pack_id = VALUES(pack_id),
                total_amount = VALUES(total_amount),
                status = VALUES(status),
                manufacturing_ending_date = VALUES(manufacturing_ending_date),
                shipping_id = VALUES(shipping_id),
                user_meli_id = VALUES(user_meli_id)
        """, (
            order_id, created_at, last_updated, pack_id,
            total_amount, status, manufacturing_ending_date, shipping_id, user_meli_id
        ))

        # Insert/update en order_items
        for item in orden.get("order_items", []):
            item_id = item.get("item", {}).get("id")
            seller_sku = item.get("item", {}).get("seller_sku")
            quantity = item.get("quantity")
            manufacturing_days = item.get("manufacturing_days")
            sale_fee = item.get("sale_fee")

            if not item_id:
                continue

            cursor.execute("""
                INSERT INTO order_items (
                    order_id, item_id, seller_sku, quantity,
                    manufacturing_days, sale_fee
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    seller_sku = VALUES(seller_sku),
                    quantity = VALUES(quantity),
                    manufacturing_days = VALUES(manufacturing_days),
                    sale_fee = VALUES(sale_fee)
            """, (
                order_id, item_id, seller_sku,
                quantity, manufacturing_days, sale_fee
            ))

    conn.commit()
    cursor.close()


def obtener_orden_por_id(access_token, order_id):
    url = f"https://api.mercadolibre.com/orders/{order_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error al obtener orden {order_id}: {response.status_code}")
        return None

    return response.json()


