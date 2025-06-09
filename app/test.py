import requests

order_id = "2000011629033904"
access_token = "APP_USR-1700552002175315-060919-b11c58926da1370f426fa87b59413bd9-2025384704"
nota = "Esta es una nota de prueba desde el script Python."

url = f"https://api.mercadolibre.com/orders/{order_id}/notes?access_token={access_token}"

payload = {
    "note": nota
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(f"Status code: {response.status_code}")

try:
    print(response.json())
except Exception as e:
    print("No se pudo parsear JSON. Respuesta cruda:")
    print(response.text)
