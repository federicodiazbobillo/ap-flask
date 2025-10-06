from flask import Blueprint
from .controllers.meli_controller import verificar_meli

def init_meli_context(bp: Blueprint):
    @bp.app_context_processor
    def inject_meli_status():
        try:
            token, _, error = verificar_meli()
            return {'meli_token_valido': error is None}
        except Exception:
            return {'meli_token_valido': False}
