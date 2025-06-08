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

def guardar_ordenes_en_db(ordenes):
    conn = get_conn()
    cursor = conn.cursor()

    for orden in ordenes:
        order_id = orden.get("id")
        date_created = orden.get("date_created")  # ISO 8601

        if not order_id or not date_created:
            continue

        cursor.execute("""
            INSERT IGNORE INTO orders (order_id, created_at)
            VALUES (%s, %s)
        """, (order_id, date_created))

    conn.commit()
    cursor.close()

