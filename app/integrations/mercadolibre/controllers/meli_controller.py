import requests
from flask import Blueprint, redirect, request
from app.db import get_conn

meli_controller = Blueprint('meli_controller', __name__)


from app.integrations.mercadolibre.services.token_service import verificar_meli


def obtener_credenciales_meli():
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM meli_access LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        raise Exception("No se encontraron credenciales en la base de datos.")

    return row['app_id'], row['secret_key'], row['user_id']

@meli_controller.route('/meli/connect')
def conectar_meli():
    try:
        app_id, _, _ = obtener_credenciales_meli()
    except Exception as e:
        return str(e), 500

    redirect_uri = 'https://TU_DOMINIO/meli/callback'
    auth_url = (
        f"https://auth.mercadolibre.com.ar/authorization?response_type=code"
        f"&client_id={app_id}&redirect_uri={redirect_uri}"
    )
    return redirect(auth_url)

@meli_controller.route('/meli/callback')
def callback_meli():
    code = request.args.get('code')
    if not code:
        return "Error: No se recibió el código de autorización", 400

    try:
        app_id, secret_key, _ = obtener_credenciales_meli()
    except Exception as e:
        return str(e), 500

    redirect_uri = 'https://TU_DOMINIO/meli/callback'
    token_url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": app_id,
        "client_secret": secret_key,
        "code": code,
        "redirect_uri": redirect_uri
    }

    response = requests.post(token_url, data=payload)
    data = response.json()

    if 'access_token' not in data:
        return f"Error al obtener token: {data}", 400

    access_token = data['access_token']
    refresh_token = data.get('refresh_token')
    user_id = data['user_id']

    # Guardar en la base de datos
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO meli_access (user_id, access_token, refresh_token, app_id, secret_key)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE access_token = VALUES(access_token), refresh_token = VALUES(refresh_token)
    """, (user_id, access_token, refresh_token, app_id, secret_key))
    conn.commit()
    cursor.close()
    conn.close()

    return "Conexión con Mercado Libre realizada correctamente."

@meli_controller.route('/meli/token')
def obtener_token_meli():
    token, user_id, error = verificar_meli()
    if error:
        return {"error": error}, 200
    return {"access_token": token, "user_id": user_id}, 200
