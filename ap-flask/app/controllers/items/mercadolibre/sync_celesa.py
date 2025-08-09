from flask import Blueprint, render_template

# Acceso a Mongo
from app.integrations.mongodb.access import (
    get_celesa_stock_collection, get_collection, ping_mongo
)

# Acceso a MySQL
from app.db import get_conn  # o get_app_connection si ese es tu estándar

# Acceso a Mercado Libre (token)
from app.integrations.mercadolibre.services.token_service import verificar_meli


sync_celesa_bp = Blueprint(
    'sync_celesa_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@sync_celesa_bp.route('/sync_celesa')
def index():
    return render_template('items/mercadolibre/sync_celesa.html')
