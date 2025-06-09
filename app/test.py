import requests

# Datos de entrada
order_id = "2000011896543284"
access_token = "APP_USR-1700552002175315-060919-b11c58926da1370f426fa87b59413bd9-2025384704"
nota = "Esta es una nota de prueba desde el script Python."

# URL del endpoint
url = f"https://api.mercadolibre.com/orders/{order_id}/notes?access_token={access_token}"

# Cuerpo de la nota
payload = {
    "note": nota
}

# Encabezados
headers = {
    "Content-Type": "application/json"
}

# Enviar la solicitud POST
response = requests.post(url, json=payload, headers=headers)

# Mostrar respuesta
print(f"Status code: {response.status_code}")
print("Respuesta:")
print(response.json())
