from flask import Blueprint

home_bp = Blueprint('home', __name__)

from .routes import home_bp
