import requests
from flask import current_app
from app.db import get_conn


def verificar_meli():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT access_token, user_id FROM meli_access LIMIT 1")
        result = cursor.fetchone()

        if not result or not result[0]:
            return False, {"error": "No se encontró un access_token válido."}

        access_token, user_id = result
        url = f"https://api.mercadolibre.com/users/me?access_token={access_token}"
        response = requests.get(url)

        if response.status_code == 200:
             return {"valido": True, "access_token": access_token}
        else:
            return { 
                "valido": False,
                "error": response.json()  # Devuelve el JSON con "error", "message", etc.
            }

    except Exception as e:
        current_app.logger.error(f"Error al verificar token de Mercado Libre: {e}")
        return False, {"error": str(e)}


# 🔁 Esto lo expone automáticamente a Jinja 
def init_token_context(app):
    @app.context_processor
    def inject_meli_token_status():
        try:
            valido, info = verificar_meli()
            return {
                'meli_token_valido': valido,
                'meli_token_info': info
            }
        except Exception as e:
            return {
                'meli_token_valido': False,
                'meli_token_info': {'error': str(e)}
            }
