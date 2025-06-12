# controllers/home/home_controller.py

from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from app.db import get_conn

home_bp = Blueprint("home", __name__, url_prefix="/")

@home_bp.route("/")
def index():
    # Leer filtro de la URL (por defecto: semana)
    filtro = request.args.get("filtro", "semana")

    # Calcular fecha de inicio según el filtro
    hoy = datetime.now().date()
    if filtro == "semana":
        fecha_inicio = hoy - timedelta(days=7)
    elif filtro == "quincena":
        fecha_inicio = hoy - timedelta(days=15)
    elif filtro == "mes":
        fecha_inicio = hoy - timedelta(days=30)
    else:
        fecha_inicio = hoy - timedelta(days=7)  # fallback

    # Consulta de ventas agrupadas por día
    ventas = db.session.execute(
        """
        SELECT DATE(created_at) AS fecha, SUM(total_amount) AS total
        FROM orders
        WHERE created_at >= :fecha_inicio
        GROUP BY DATE(created_at)
        ORDER BY fecha ASC
        """,
        {"fecha_inicio": fecha_inicio}
    ).fetchall()

    # Convertir a formato JS
    fechas = [v["fecha"].strftime("%Y-%m-%d") for v in ventas]
    totales = [float(v["total"]) for v in ventas]

    return render_template("home/index.html", fechas=fechas, totales=totales, filtro=filtro)
