import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:////app/db_data/auth.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False