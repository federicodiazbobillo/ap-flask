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

            # Verificar si ya existe el registro
            cursor.execute("""
                SELECT 1 FROM order_items
                WHERE order_id = %s AND item_id = %s
            """, (order_id, item_id))

            existe = cursor.fetchone()

            if existe:
                # Si existe, hacer UPDATE
                cursor.execute("""
                    UPDATE order_items
                    SET seller_sku = %s,
                        quantity = %s,
                        manufacturing_days = %s,
                        sale_fee = %s
                    WHERE order_id = %s AND item_id = %s
                """, (
                    seller_sku, quantity, manufacturing_days, sale_fee,
                    order_id, item_id
                ))
            else:
                # Si no existe, hacer INSERT
                cursor.execute("""
                    INSERT INTO order_items (
                        order_id, item_id, seller_sku, quantity,
                        manufacturing_days, sale_fee
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    order_id, item_id, seller_sku,
                    quantity, manufacturing_days, sale_fee
                ))


    conn.commit()
    cursor.close()


def obtener_orden_por_id(access_token, order_id):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Primer intento: buscar como ID de orden
    url_orden = f"https://api.mercadolibre.com/orders/{order_id}"
    response = requests.get(url_orden, headers=headers)

    if response.status_code == 200:
        return response.json()

    # Si no existe como orden, intentar como pack_id
    if response.status_code == 404:
        url_pack = f"https://api.mercadolibre.com/packs/{order_id}"
        resp_pack = requests.get(url_pack, headers=headers)

        if resp_pack.status_code == 200:
            data = resp_pack.json()
            ordenes = data.get("orders", [])
            if ordenes:
                real_order_id = ordenes[0].get("id")
                # Segundo intento con el ID real
                response2 = requests.get(f"https://api.mercadolibre.com/orders/{real_order_id}", headers=headers)
                if response2.status_code == 200:
                    return response2.json()
                else:
                    print(f"❌ Error al obtener orden desde pack {real_order_id}: {response2.status_code}")
                    return None
        else:
            print(f"❌ Error al buscar como pack_id {order_id}: {resp_pack.status_code}")
            return None

    print(f"❌ Error desconocido al buscar orden {order_id}: {response.status_code}")
    return None



