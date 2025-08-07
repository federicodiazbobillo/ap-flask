from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import get_conn


items_mercadolibre_bp = Blueprint(
    'items_mercadolibre_bp',
    __name__,
    template_folder='app/templates/items/mercadolibre'
)

@items_mercadolibre_bp.route('/sin_isbn')
def items_sin_isbn():
    return "🟢 Items sin ISBN funcionando"
