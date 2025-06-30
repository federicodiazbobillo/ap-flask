from flask import Blueprint, render_template
from pymongo import MongoClient
from app.db import get_conn

bp = Blueprint("publicador_arnoia", __name__, url_prefix="/items/mercadolibre/publicador_arnoia")

@bp.route("/")
def index():
    # MongoDB
    mongo = MongoClient("mongodb://localhost:27017")
    arnoia_db = mongo["arnoia"]
    productos = arnoia_db["productos"]

    mongo_isbns = set()
    detalles = {}
    for doc in productos.find({"isbn": {"$exists": True, "$ne": ""}}, {"isbn": 1, "titulo": 1, "precio": 1, "editorial": 1}):
        isbn = doc["isbn"]
        mongo_isbns.add(isbn)
        detalles[isbn] = {
            "titulo": doc.get("titulo", ""),
            "precio": doc.get("precio", ""),
            "editorial": doc.get("editorial", "")
        }

    # MySQL
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT isbn FROM items_meli WHERE isbn IS NOT NULL AND isbn != ''")
    meli_isbns = set(row[0] for row in cursor.fetchall())

    # Comparación
    faltantes = mongo_isbns - meli_isbns
    resultados = [{ "isbn": isbn, **detalles[isbn] } for isbn in list(faltantes)[:50]]

    return render_template("items/mercadolibre/catalogador/publicador_arnoia.html", resultados=resultados)
