import requests
import time
from decimal import Decimal
from app.db import get_conn
from app.integrations.mercadolibre.services.token_service import verificar_meli
import pymysql

def guardar_envios(shipping_ids, _access_token):
    if not shipping_ids:
        return

    conn = get_conn()
    cursor = conn.cursor()

    for shipping_id in set(shipping_ids):
        time.sleep(1)

        if not shipping_id:
            continue

        access_token, user_id, error = verificar_meli()
        if error:
            print(f"❌ Token error en shipment_id {shipping_id}: {error}")
            return

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.get(f"https://api.mercadolibre.com/shipments/{shipping_id}", headers=headers)
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

        access_token, user_id, error = verificar_meli()
        if error:
            print(f"❌ Token error antes del SLA en shipment_id {shipping_id}: {error}")
            return
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        delayed = None
        sla_response = requests.get(f"https://api.mercadolibre.com/shipments/{shipping_id}/sla", headers=headers)
        if sla_response.status_code == 200:
            sla_data = sla_response.json()
            if isinstance(sla_data, dict) and "status" in sla_data:
                delayed = str(sla_data["status"])

        print(f"Insertando shipment_id {shipping_id} con delayed: {delayed} {list_cost}")

        if list_cost is None or status is None or substatus is None:
            continue

        try:
            cursor.execute("""
                INSERT INTO shipments (shipping_id, list_cost, status, substatus, delay)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    list_cost = VALUES(list_cost),
                    status = VALUES(status),
                    substatus = VALUES(substatus),
                    delay = VALUES(delay)
            """, (shipping_id, list_cost, status, substatus, delayed))
            conn.commit()

        except pymysql.OperationalError as e:
            if e.args[0] == 1205:
                print(f"⚠️ Timeout en shipment_id {shipping_id}, reintentando en 1 segundo...")
                #time.sleep(0.1)
                try:
                    cursor.execute("""
                        INSERT INTO shipments (shipping_id, list_cost, status, substatus, delay)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            list_cost = VALUES(list_cost),
                            status = VALUES(status),
                            substatus = VALUES(substatus),
                            delay = VALUES(delay)
                    """, (shipping_id, list_cost, status, substatus, delayed))
                    conn.commit()
                    print(f"✅ Reintento exitoso de shipment_id {shipping_id}")
                except Exception as e2:
                    conn.rollback()
                    print(f"❌ Falló el reintento de shipment_id {shipping_id}: {e2}")
                    break  # 🔴 DETIENE la ejecución completa
            else:
                conn.rollback()
                print(f"❌ Error operativo al insertar shipment_id {shipping_id}: {e}")
                break
        except Exception as e:
            conn.rollback()
            print(f"❌ Error general al insertar shipment_id {shipping_id}: {e}")
            break

    cursor.close()
 