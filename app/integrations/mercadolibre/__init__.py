from flask import Blueprint
from app.integrations.mercadolibre.verificar_token import init_token_context

mercadolibre_bp = Blueprint('mercadolibre', __name__)

def init_app(app):
    init_token_context(app)
