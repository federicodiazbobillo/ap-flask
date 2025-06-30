import requests
from flask import Blueprint, render_template, request

# 🔧 Configuración
LOCAL_API_TOKEN = "clave_super_secreta_456"
LOCAL_API_BASE_URL = "http://sys.apricor.com.mx:33944/api/libro"

stock_suppliers_bp = Blueprint('purchases', __name__, url_prefix='/purchases')

@stock_suppliers_bp.route('/stock-suppliers')
def stock_suppliers():
    isbn = request.args.get("isbn", "").strip()
    libro = None

    if isbn:
        libro = obtener_stock_por_isbn(isbn)

    return render_template("purchases/stock_suppliers.html", libro=libro)

def obtener_stock_por_isbn(isbn):
    local_api_url = f"{LOCAL_API_BASE_URL}?isbn={isbn}"
    try:
        local_resp = requests.get(
            local_api_url,
            headers={"Authorization": f"Bearer {LOCAL_API_TOKEN}"},
            timeout=10
        )
        local_resp.raise_for_status()
        libro_info = local_resp.json()
        return libro_info
    except requests.RequestException as e:
        print(f"Error al consultar API local: {e}")
        return None
