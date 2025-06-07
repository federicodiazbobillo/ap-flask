from flask import current_app
from app import mysql

def get_conn():
    return mysql.connection
