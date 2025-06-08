from flask import Blueprint
from app.controllers.orders.orders_costos_controller import orders_costos_bp
from app.controllers.orders.orders_logistica_controller import orders_logistica_bp

orders_bp = Blueprint('orders_bp', __name__)
