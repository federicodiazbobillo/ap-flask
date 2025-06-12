from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from app.db import get_conn

home_bp = Blueprint("home", __name__, url_prefix="/")

@home_bp.route("/")
def index():
    filtro = request.args.get("filtro", "semana")
    hoy = datetime.now().date()

    if filtro == "semana":
        fecha_inicio = hoy - timedelta(days=7)
    elif filtro == "quincena":
        fecha_inicio = hoy - timedelta(days=15)
    elif filtro == "mes":
        fecha_inicio = hoy - timedelta(days=30)
    else:
        fecha_inicio = hoy - timedelta(days=7)

    query = """
        SELECT DATE(created_at) AS fecha, SUM(total_amount) AS total
        FROM orders
        WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY fecha ASC
    """

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(query, (fecha_inicio,))
    ventas = cursor.fetchall()

    fechas = [v[0].strftime("%Y-%m-%d") for v in ventas]
    totales = [float(v[1]) for v in ventas]

    return render_template("home/index.html", fechas=fechas, totales=totales, filtro=filtro)
