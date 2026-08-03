import os
import tempfile

# Deben definirse ANTES de importar app.config (Flask-SQLAlchemy 3.x crea los
# engines en init_app y no refleja cambios posteriores al config).
_db_dir = tempfile.mkdtemp(prefix='auth_db_test_')
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_db_dir, 'auth.db')}"
os.environ['JWT_KEYS_DIR'] = tempfile.mkdtemp(prefix='jwt_keys_test_')

import pytest

from app import create_app
from app.models import db
from app.rate_limiter import rate_limiter
import app.key_manager as key_manager


@pytest.fixture(autouse=True)
def _entorno_aislado(monkeypatch, tmp_path):
    # Evita escribir la clave pública dentro del repo y resetea el rate limiter.
    def _app_dir_prueba():
        app_dir = tmp_path / 'app'
        app_dir.mkdir(exist_ok=True)
        return app_dir
    monkeypatch.setattr(key_manager, '_app_dir', _app_dir_prueba)
    monkeypatch.setattr(rate_limiter, '_hits', {})


@pytest.fixture()
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
    with app.test_client() as c:
        yield c
    with app.app_context():
        db.session.remove()
        db.drop_all()
