import requests
from flask import Blueprint, render_template
from app.integrations.mercadolibre.services.token_service import verificar_meli

promociones_bp = Blueprint("promociones", __name__, url_prefix="/meli/promociones")

@promociones_bp.route("/")
def listar_promociones():
    access_token, user_id, error = verificar_meli()

    if error:
        print("Error al verificar token:", error)
        return "Error al verificar token", 500

    url = f"https://api.mercadolibre.com/seller-promotions/users/{user_id}?app_version=v2&access_token={access_token}"
    print("Consultando:", url)

    try:
        resp = requests.get(url)
        print("Status code:", resp.status_code)

        if resp.status_code != 200:
            print("Respuesta inválida:", resp.text)
            return "Error al obtener promociones", 500

        data = resp.json()
        promociones = data.get("promotions", [])
        print(f"Promociones encontradas: {len(promociones)}")
    except Exception as e:
        print("Excepción al consultar promociones:", e)
        promociones = []

    return render_template("items/mercadolibre/promociones/index.html", promociones=promociones)
