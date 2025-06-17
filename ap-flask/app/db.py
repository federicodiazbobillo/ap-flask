
from app.extensions import mysql

def get_conn():
    return mysql.connection
