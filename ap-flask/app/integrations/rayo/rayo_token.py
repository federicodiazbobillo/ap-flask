# app/integrations/rayo/rayo_token.py
# -*- coding: utf-8 -*-
import os
import requests
from flask import Blueprint, jsonify, current_app

bp = Blueprint("rayo_bp", __name__, url_prefix="/rayo")

def _cfg():
    return os.getenv("URL_RAYO"), os.getenv("APIRAYO")

@bp.route("/ping", methods=["GET"], endpoint="rayo_ping")
def rayo_ping():
    url_rayo, api_rayo = _cfg()

    if not url_rayo or not api_rayo:
        current_app.logger.warning("[RAYO] Faltan env: URL_RAYO o APIRAYO")
        return jsonify(ok=False, error="Faltan env: URL_RAYO o APIRAYO", code=500), 200

    # En tu .env poné URL_RAYO=https://cerebro.techrayo.com/api/rest
    endpoint = url_rayo.rstrip("/") + "/auth"
    headers = {"x-api-key": api_rayo}

    try:
        resp = requests.post(endpoint, headers=headers, timeout=6)
        if resp.ok:
            return jsonify(ok=True), 200
        msg = f"{resp.status_code}: {resp.text[:200]}"
        current_app.logger.warning(f"[RAYO] Auth no OK -> {msg}")
        return jsonify(ok=False, error=msg, code=resp.status_code), 200

    except requests.RequestException as e:
        current_app.logger.exception(f"[RAYO] RequestException: {e}")
        return jsonify(ok=False, error=f"request_error: {e}", code=502), 200
