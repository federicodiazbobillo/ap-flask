# app/db.py
from flask import current_app
def get_conn():
    return current_app.extensions['mysql'].connection
