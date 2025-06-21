from flask import Blueprint, render_template, request, redirect, url_for, flash
from .listado import obtener_items
from .catalogar import procesar_catalogacion
from app.integrations.mercadolibre.services.token_service import verificar_meli

catalogador_bp = Blueprint(
    'catalogador_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@catalogador_bp.route('/items/mercadolibre')
def items():
    access_token, user_id, error = verificar_meli()
    if error:
        flash(f"Error al obtener token: {error}", "danger")
        return render_template('items/mercadolibre/items.html', items=[], total=0, page=1, limit=50)
    
    context = obtener_items(request, access_token)
    return render_template('items/mercadolibre/items.html', **context)

@catalogador_bp.route('/catalogar', methods=['POST'])
def catalogar_items():
    access_token, user_id, error = verificar_meli()
    if error:
        flash(f"Error al obtener token: {error}", "danger")
        return redirect(url_for("catalogador_bp.items"))
    
    return procesar_catalogacion(request, access_token)
