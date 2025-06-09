from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta
from app.db import get_conn
from app.integrations.mercadolibre.services.token_service import verificar_meli
from app.integrations.mercadolibre.services.orders_service import (
    obtener_ordenes,
    obtener_orden_por_id,
    guardar_ordenes_en_db
)

sync_mercadolibre_bp = Blueprint('sync_mercadolibre', __name__, url_prefix='/sync/mercadolibre')

@sync_mercadolibre_bp.route('/')
def index(): 
    return render_template('sync/sync_mercadolibre.html')

@sync_mercadolibre_bp.route('/sync')
def sync_orders():
    access_token, user_id, error = verificar_meli()
    if error:
        return jsonify({"error": True, "message": f"❌ Token error: {error}"}), 401

    # Optional parameter: sync by ID
    order_id = request.args.get("id")
    if order_id:
        order = obtener_orden_por_id(access_token, order_id)
        if not order:
            return jsonify({
                "error": True,
                "message": f"❌ Order {order_id} not found or unavailable."
            }), 404

        guardar_ordenes_en_db([order], user_meli_id=user_id)
        return jsonify({
            "error": False,
            "message": f"✅ Order {order_id} synced successfully.",
            "orders": [order_id]
        })

    # Period or custom date range
    period = request.args.get("period")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    if not (date_from and date_to) and period:
        now = datetime.utcnow()
        if period == "month":
            date_from = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            date_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif period == "48h":
            date_from = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
            date_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    result = obtener_ordenes(access_token, user_id, date_from, date_to)

    if result["error"]:
        return jsonify({
            "error": True,
            "message": f"❌ Sync error: {result['message']}"
        }), 500

    orders = result["ordenes"]
    return jsonify({
        "error": False,
        "message": f"✅ {len(orders)} orders synced.",
        "orders": [order.get("id") for order in orders]
    })
