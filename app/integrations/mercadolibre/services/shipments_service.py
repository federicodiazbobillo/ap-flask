# app/integrations/mercadolibre/services/shipments_service.py
import requests
from decimal import Decimal
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
            try:
                list_cost = round(Decimal(str(list_cost)), 2)
            except Exception as e:
                print(f"⚠️ Error al convertir list_cost en shipment_id {shipping_id}: {e}")
                continue

        status = data.get("status")
        substatus = str(data.get("substatus")) if data.get("substatus") else None

        # Segunda consulta para obtener 'delayed'
        delayed = None
        sla_url = f"https://api.mercadolibre.com/shipments/{shipping_id}/sla"
        sla_response = requests.get(sla_url, headers=headers)
        if sla_response.status_code == 200:
            sla_data = sla_response.json()
            if isinstance(sla_data, dict) and "status" in sla_data:
                delayed = str(sla_data["status"])

        print(f"Insertando shipment_id {shipping_id} con delayed: {delayed} {list_cost}")

        if list_cost is None or status is None or substatus is None:
            continue

        try:
            cursor.execute("""
                INSERT INTO shipments (shipping_id, list_cost, status, substatus, delayed)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    list_cost = VALUES(list_cost),
                    status = VALUES(status),
                    substatus = VALUES(substatus),
                    delayed = VALUES(delayed)
            """, (shipping_id, list_cost, status, substatus, delayed))
        except Exception as e:
            print(f"❌ Error al insertar shipment_id {shipping_id}: {e}")

    conn.commit()
    cursor.close()
