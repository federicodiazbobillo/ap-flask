from flask import Blueprint, render_template, redirect, url_for, flash

# Blueprint con nombre único y claro
items_meli_bp = Blueprint(
    'items_meli_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

# Ruta principal: vista de items
@items_meli_bp.route('/items/mercadolibre')
def items():
    return render_template('items/mercadolibre/items.html')

