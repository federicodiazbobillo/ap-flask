from app.extensions import mysql
from flask import current_app
import requests

def verificar_meli():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT access_token, user_id FROM meli_access LIMIT 1")
        result = cursor.fetchone()
        
        if not result or not result[0]:
            current_app.logger.warning("No se encontró un access_token válido en la base de datos.")
            return False

        access_token, user_id = result
        url = f"https://api.mercadolibre.com/users/me?access_token={access_token}"
        response = requests.get(url)

        if response.status_code == 200:
            return True  # o incluso response.json() si querés más info
        else:
            current_app.logger.warning(f"Token inválido o expirado para user_id {user_id}. Status: {response.status_code}")
            return False

    except Exception as e:
        current_app.logger.error(f"Error al verificar token de Mercado Libre: {e}")
        return False
