from flask import Blueprint, jsonify
import time

sync_orders_bp = Blueprint('sync_orders', __name__, url_prefix='/ordenes')

@sync_orders_bp.route('/sincronizar')
def sincronizar_ordenes():
    time.sleep(5)  # Simula carga
    return jsonify({"message": "✅ Órdenes sincronizadas correctamente."})
