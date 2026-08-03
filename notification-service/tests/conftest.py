import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def _sin_consumidor(monkeypatch):
    # Evita que el lifespan arranque el hilo de RabbitMQ durante los tests.
    monkeypatch.setattr('app.main.start_rabbitmq_consumer', lambda: None)
