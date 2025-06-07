import os
from flask import Flask
from flask_mysqldb import MySQL
from app.config import Config
from app.db import get_conn  # ACCESO ÚNICO
from app.integrations.mercadolibre.verificar_token import verificar_meli
from app.utils.blueprint_loader import register_blueprints

mysql = MySQL()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    mysql.init_app(app)

    # Verificar conexión a la base de datos
    try:
        with app.app_context():
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            app.jinja_env.globals['db_connected'] = True
    except Exception:
        app.jinja_env.globals['db_connected'] = False

    # Verificar token de Mercado Libre
    try:
        token_valido = verificar_meli()
        app.jinja_env.globals['meli_token_valido'] = token_valido
    except Exception:
        app.jinja_env.globals['meli_token_valido'] = False

    # Registro automático de blueprints
    register_blueprints(app, 'app.controllers', os.path.join(app.root_path, 'controllers'))
    register_blueprints(app, 'app.integrations', os.path.join(app.root_path, 'integrations'))


    return app
