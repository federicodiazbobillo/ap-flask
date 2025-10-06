import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables desde .env

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'clave-por-defecto')
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'test')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
