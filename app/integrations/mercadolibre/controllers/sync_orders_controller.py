from flask import Blueprint, jsonify, request
from app.db import get_conn
from app.integrations.mercadolibre.services.token_service import verificar_meli
from app.integrations.mercadolibre.services.orders_service import (
    obtener_ordenes,
    obtener_orden_por_id,
    guardar_ordenes_en_db
)

sync_orders_bp = Blueprint('sync_orders', __name__, url_prefix='/ordenes')

@sync_orders_bp.route('/sincronizar')
def sincronizar_ordenes():
    access_token, user_id, error = verificar_meli()
    if error:
        return jsonify({"error": True, "message": f"❌ Error de token: {error}"}), 401

    # Parámetro opcional: sincronizar orden por ID
    order_id = request.args.get("id")
    if order_id:
        orden = obtener_orden_por_id(access_token, order_id)
        if not orden:
            return jsonify({
                "error": True,
                "message": f"❌ No se encontró la orden {order_id} o no está disponible."
            }), 404

        guardar_ordenes_en_db([orden])
        return jsonify({
            "error": False,
            "message": f"✅ Orden {order_id} sincronizada correctamente.",
            "ordenes": [order_id]
        })

    # Parámetros opcionales: rango de fechas
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    resultado = obtener_ordenes(access_token, user_id, date_from, date_to)

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
