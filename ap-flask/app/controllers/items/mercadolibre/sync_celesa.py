from flask import Blueprint, render_template

sync_celesa_bp = Blueprint(
    'sync_celesa_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@sync_celesa_bp.route('/sync_celesa')
def index():
    return render_template('items/mercadolibre/sync_celesa.html')
