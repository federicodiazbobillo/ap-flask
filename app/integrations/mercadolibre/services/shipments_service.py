# app/integrations/mercadolibre/services/shipments_service.py
import requests
from app.db import get_conn

def guardar_envios(shipping_ids, access_token):
    if not shipping_ids:
        return

    conn = get_conn()
    cursor = conn.cursor()

    url_base = "https://api.mercadolibre.com/shipments/"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    for shipping_id in set(shipping_ids):
        if not shipping_id:
            continue

        url = f"{url_base}{shipping_id}"
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Error con shipping_id {shipping_id}: {response.status_code}")
            continue

        data = response.json()
        list_cost = data.get("shipping_option", {}).get("list_cost")
        if list_cost is not None:
            list_cost = float(list_cost)
        status = data.get("status")
        substatus = data.get("substatus")

        # Segunda consulta para obtener 'delayed'
        delayed = None
        sla_url = f"https://api.mercadolibre.com/shipments/{shipping_id}/sla"
        sla_response = requests.get(sla_url, headers=headers)
        if sla_response.status_code == 200:
            sla_data = sla_response.json()
            if "status" in sla_data:
                delayed = sla_data["status"]
            # Si solo hay 'code', delayed queda como None
        print(f"Insertando shipment_id {shipping_id} con delayed: {delayed} {list_cost}")  # <-- Agregado
        
        if list_cost is None or status is None or substatus is None: 
            continue

        cursor.execute("""
            INSERT INTO shipments (shipping_id, list_cost, status, substatus, delayed)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                list_cost = VALUES(list_cost),
                status = VALUES(status),
                substatus = VALUES(substatus),
                delayed = VALUES(delayed)
        """, (shipping_id, list_cost, status, substatus, delayed))

    conn.commit()
    cursor.close()
