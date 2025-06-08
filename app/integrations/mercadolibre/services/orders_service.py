import requests
from app.db import get_conn

def obtener_ordenes(access_token, user_id):
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

    guardar_ordenes_en_db(ordenes)

    return {
        "error": False,
        "ordenes": ordenes
    }

from app.db import get_conn

def guardar_ordenes_en_db(ordenes):
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
                total_amount, status, manufacturing_ending_date, shipping_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_updated = VALUES(last_updated),
                pack_id = VALUES(pack_id),
                total_amount = VALUES(total_amount),
                status = VALUES(status),
                manufacturing_ending_date = VALUES(manufacturing_ending_date),
                shipping_id = VALUES(shipping_id)
        """, (
            order_id,
            created_at,
            last_updated,
            pack_id,
            total_amount,
            status,
            manufacturing_ending_date,
            shipping_id
        ))

    conn.commit()
    cursor.close()

