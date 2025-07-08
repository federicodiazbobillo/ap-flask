import requests
from decimal import Decimal

LOCAL_API_TOKEN = "clave_super_secreta_456"
LOCAL_API_BASE_URL = "http://sys.apricor.com.mx:33944/api"

def obtener_stock_por_isbn(isbn):
    """Consulta la API local por un solo ISBN (versión antigua, aún útil si querés usar individual)."""
    url = f"{LOCAL_API_BASE_URL}/libro?isbn={isbn}"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {LOCAL_API_TOKEN}"}, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"Error API local: {e}")
        return None

def obtener_stock_por_lote(isbns):
    """Consulta la API local por un lote de ISBNs."""
    url = f"{LOCAL_API_BASE_URL}/libro-lote"
    try:
        resp = requests.post(
            url,
            json={"isbns": isbns},
            headers={"Authorization": f"Bearer {LOCAL_API_TOKEN}"},
            timeout=8600
        )
        resp.raise_for_status()
        return resp.json()  # dict con cada ISBN como clave
    except requests.RequestException as e:
        print(f"Error API local (lote): {e}")
        return {}

def seleccionar_mejor_proveedor(data):
    disponibilidad = data.get("disponibilidad", {})
    precios = data.get("precio_final", {})

    mejor = {
        "proveedor": "❌",
        "stock": None,
        "precio": None
    }

    candidatos = []

    for proveedor in ["arnoia", "celesa"]:
        stock_raw = disponibilidad.get(proveedor)
        precio_raw = precios.get(proveedor)

        if stock_raw is None or precio_raw is None:
            continue

        try:
            stock = int(stock_raw)
            precio = Decimal(str(precio_raw))
        except (ValueError, TypeError):
            continue

        if stock > 0:
            candidatos.append({
                "proveedor": proveedor,
                "stock": stock,
                "precio": precio
            })

    if candidatos:
        mejor = max(candidatos, key=lambda x: x["stock"])

    return mejor
