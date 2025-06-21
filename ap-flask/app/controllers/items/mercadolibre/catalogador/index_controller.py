from flask import Blueprint, render_template, request
from .listado import obtener_items
from .catalogar import procesar_catalogacion

items_meli_bp = Blueprint(
    'items_meli_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@items_meli_bp.route('/items/mercadolibre')
def items():
    context = obtener_items(request)
    return render_template('items/mercadolibre/items.html', **context)

@items_meli_bp.route('/catalogar', methods=['POST'])
def catalogar_items():
    return procesar_catalogacion(request)
