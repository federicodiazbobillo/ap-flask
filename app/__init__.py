from flask import Flask
from flask_mysqldb import MySQL
from app.config import Config
import MySQLdb

mysql = MySQL()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    mysql.init_app(app)

    # Verificar conexión a la base de datos
    try:
        with app.app_context():
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            app.jinja_env.globals['db_connected'] = True
    except Exception:
        app.jinja_env.globals['db_connected'] = False

    from app.controllers.auth import auth_bp
    from app.controllers.home import home_bp
    from app.controllers.orders import orders_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(orders_bp)

    return app
