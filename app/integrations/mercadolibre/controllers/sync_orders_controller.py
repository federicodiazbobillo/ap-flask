from flask import Blueprint, jsonify
from app.db import get_conn
from app.integrations.mercadolibre.services.token_service import verificar_meli
from app.integrations.mercadolibre.services.orders_service import obtener_ordenes

sync_orders_bp = Blueprint('sync_orders', __name__, url_prefix='/ordenes')

@sync_orders_bp.route('/sincronizar')
def sincronizar_ordenes():
    access_token, user_id, error = verificar_meli()
    if error:
        return jsonify({"error": True, "message": f"❌ Error de token: {error}"}), 401

    resultado = obtener_ordenes(access_token, user_id)

    if resultado["error"]:
        return jsonify({
            "error": True,
            "message": f"❌ Error al sincronizar: {resultado['message']}"
        }), 500

    ordenes = resultado["ordenes"]
    return jsonify({
        "error": False,
        "message": f"✅ {len(ordenes)} órdenes sincronizadas.",
        "ordenes": [orden.get("id") for orden in ordenes]
    })
