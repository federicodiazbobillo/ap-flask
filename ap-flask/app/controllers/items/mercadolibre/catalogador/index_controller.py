from flask import Blueprint, render_template, request
from .listado import obtener_items
from .catalogar import procesar_catalogacion

catalogador_bp = Blueprint(
    'catalogador_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@catalogador_bp.route('/items/mercadolibre')
def items():
    context = obtener_items(request)
    return render_template('items/mercadolibre/items.html', **context)

@catalogador_bp.route('/catalogar', methods=['POST'])
def catalogar_items():
    return procesar_catalogacion(request)
