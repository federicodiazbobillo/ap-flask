from flask import Flask
from flask_mysqldb import MySQL
from app.config import Config

mysql = MySQL()

def create_app():
    # Asegura que Flask encuentre correctamente static/ y templates/
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)

    mysql.init_app(app)

    from app.controllers.auth import auth_bp
    from app.controllers.home import home_bp
    from app.controllers.orders import orders_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(orders_bp)

    return app
