import requests
from app.db import get_conn

def verificar_meli():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, access_token, refresh_token, app_id, secret_key FROM meli_access LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    

    if not row:
        return None, None, "No hay credenciales de Mercado Libre en la base de datos."

    user_id, access_token, refresh_token, app_id, secret_key = row

    # Verificar si el token aún es válido
    r = requests.get("https://api.mercadolibre.com/users/me", headers={
        "Authorization": f"Bearer {access_token}"
    })

    if r.status_code == 200:
        return access_token, user_id, None

    # Si el token expiró, intentar refrescarlo
    token_url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": app_id,
        "client_secret": secret_key,
        "refresh_token": refresh_token
    }

    response = requests.post(token_url, data=payload)
    data = response.json()

    if 'access_token' not in data:
        return None, None, f"Error al refrescar token: {data}"

    new_access_token = data['access_token']
    new_refresh_token = data.get('refresh_token')

    # Guardar nuevo token
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE meli_access
        SET access_token = %s, refresh_token = %s
        WHERE user_id = %s
    """, (new_access_token, new_refresh_token, user_id))
    conn.commit()
    cursor.close()
    

    return new_access_token, user_id, None
