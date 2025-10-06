import os
from flask import Flask
from app.config import Config
from app.db import get_conn
from app.utils.blueprint_loader import register_blueprints
from app.extensions import mysql
from dotenv import load_dotenv


def create_app():
    load_dotenv()
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    mysql.init_app(app)

    # Validar conexión a la base de datos
    try:
        with app.app_context():
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            app.jinja_env.globals['db_connected'] = True
    except Exception:
        app.jinja_env.globals['db_connected'] = False

    # Registrar blueprints automáticamente
    register_blueprints(app, 'app.controllers', os.path.join(app.root_path, 'controllers'))
    register_blueprints(app, 'app.integrations', os.path.join(app.root_path, 'integrations'))

    return app
 