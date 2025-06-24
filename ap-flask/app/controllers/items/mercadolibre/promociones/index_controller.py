# promociones_controller.py
import requests
from flask import Blueprint, render_template
from app.integrations.mercadolibre.services.token_service import verificar_meli

promociones_bp = Blueprint("promociones", __name__, url_prefix="/meli/promociones")

@promociones_bp.route("/")
def listar_promociones():
    access_token, user_id, error = verificar_meli()
    url = f"https://api.mercadolibre.com/seller-promotions/users/2025384704?app_version=v2&access_token={access_token}"
    resp = requests.get(url)
    promociones = resp.json().get("promotions", [])
    return render_template("items/mercadolibre/promociones/index.html", promociones=promociones)
