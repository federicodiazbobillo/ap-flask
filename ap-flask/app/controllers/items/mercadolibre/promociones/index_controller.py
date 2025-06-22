from flask import Blueprint, render_template

meli_promociones_bp = Blueprint(
    'meli_promociones_bp',
    __name__,
    url_prefix='/items/mercadolibre/promociones',
    template_folder='app/templates/items/mercadolibre/promociones'
)

@meli_promociones_bp.route('/')
def index():
    return render_template('items/mercadolibre/promociones/index.html')
