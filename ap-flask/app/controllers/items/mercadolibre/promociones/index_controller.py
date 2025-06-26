import requests
from flask import Blueprint, render_template, request, redirect, url_for
from app.integrations.mercadolibre.services.token_service import verificar_meli
from datetime import datetime

promociones_bp = Blueprint("promociones", __name__, url_prefix="/meli/promociones")


def formatear_fecha(fecha_iso):
    try:
        return datetime.fromisoformat(fecha_iso.replace("Z", "+00:00")).strftime('%d/%m/%Y')
    except Exception:
        return fecha_iso


def contar_items_en_promocion(promotion_id, promotion_type, access_token):
    base_url = "https://api.mercadolibre.com/seller-promotions/promotions"
    headers = {"Authorization": f"Bearer {access_token}"}

    def get_total(status):
        try:
            url = f"{base_url}/{promotion_id}/items"
            params = {
                "promotion_type": promotion_type,
                "status": status,
                "attributes": "paging",
                "app_version": "v2"
            }
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json().get("paging", {}).get("total", 0)
        except Exception as e:
            print(f"Error obteniendo {status} para {promotion_id}: {e}")
        return 0

    elegibles = get_total("candidate")
    participando = get_total("started")
    return elegibles, participando


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
        promociones = data.get("results", [])

        for promo in promociones:
            promo["start_date"] = formatear_fecha(promo.get("start_date", ""))
            promo["finish_date"] = formatear_fecha(promo.get("finish_date", ""))

            elegibles, participando = contar_items_en_promocion(
                promo["id"],
                promo["type"],
                access_token
            )
            promo["elegibles"] = elegibles
            promo["participando"] = participando

    except Exception as e:
        print("Excepción al consultar promociones:", e)
        promociones = []

    return render_template("items/mercadolibre/promociones/index.html", promociones=promociones)


@promociones_bp.route("/<promotion_id>/items")
def ver_items(promotion_id):
    access_token, user_id, error = verificar_meli()
    if error:
        return "Error al verificar token", 500

    promotion_type = request.args.get("promotion_type", "")
    status = request.args.get("status", "candidate")
    search_after = request.args.get("search_after", None)

    url = f"https://api.mercadolibre.com/seller-promotions/promotions/{promotion_id}/items"
    params = {
        "promotion_type": promotion_type,
        "status": status,
        "limit": 50,
        "app_version": "v2"
    }
    if search_after:
        params["search_after"] = search_after

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            print("❌ Error al obtener ítems:", resp.text)
            return "Error al obtener ítems de promoción", 500

        data = resp.json()
        items = data.get("results", [])
        paging = data.get("paging", {})
        next_search_after = paging.get("searchAfter")

        # ⚠️ Reintentar si viene vacío pero hay más resultados
        if not items and next_search_after:
            print("🔁 Resultados vacíos. Reintentando con search_after...")
            params["search_after"] = next_search_after
            resp = requests.get(url, headers=headers, params=params)
            data = resp.json()
            items = data.get("results", [])
            next_search_after = data.get("paging", {}).get("searchAfter")

    except Exception as e:
        print("❌ Excepción al obtener ítems:", e)
        items = []
        next_search_after = None

    return render_template(
        "items/mercadolibre/promociones/listar.html",
        items=items,
        promotion_id=promotion_id,
        status=status,
        promotion_type=promotion_type,
        search_after=next_search_after
    )


@promociones_bp.route("/aplicar", methods=["POST"])
def aplicar_descuentos():
    access_token, user_id, error = verificar_meli()
    if error:
        print("Error al verificar token:", error)
        return "Error al verificar token", 500

    promotion_id = request.form.get("promotion_id")
    promotion_type = request.form.get("promotion_type")
    items_aplicar = request.form.getlist("items_on[]")
    items_excluir = request.form.getlist("items_off[]")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Aplicar descuentos (ON)
    for item in items_aplicar:
        try:
            item_id, price = item.split("|")
            url = f"https://api.mercadolibre.com/seller-promotions/items/{item_id}?app_version=v2"
            data = {
                "promotion_id": promotion_id,
                "promotion_type": promotion_type,
                "deal_price": float(price)
            }
            print(f"▶ Aplicando descuento a {item_id}: {data}")
            response = requests.post(url, headers=headers, json=data)
            print("Status code:", response.status_code)
            print("Response text:", response.text)
        except Exception as e:
            print(f"❌ Error al aplicar descuento: {e}")

    # Excluir ítems (OFF)
    for item in items_excluir:
        try:
            item_id = item  # solo ID
            url = f"https://api.mercadolibre.com/seller-promotions/items/{item_id}?app_version=v2"
            data = {
                "promotion_id": promotion_id,
                "promotion_type": promotion_type
            }
            print(f"⛔ Excluyendo item {item_id}")
            response = requests.delete(url, headers=headers, json=data)
            print("Status code:", response.status_code)
            print("Response text:", response.text)
        except Exception as e:
            print(f"❌ Error al excluir item: {e}")

    return redirect(url_for("promociones.ver_items", promotion_id=promotion_id, promotion_type=promotion_type))

