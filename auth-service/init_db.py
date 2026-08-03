import os

from app import create_app
from app.models import db
from app.key_manager import ensure_keys

if __name__ == "__main__":
    os.makedirs("/app/db_data", exist_ok=True)
    ensure_keys()
    app = create_app()
    with app.app_context():
        db.create_all()
        print("[SISTEMA] Base de datos de usuarios e índices inicializados en db_data correctamente.")
