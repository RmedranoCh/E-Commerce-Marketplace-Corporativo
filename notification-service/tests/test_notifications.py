import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_email_notifier_genera_correo(capsys):
    from app.email_notifier import EmailNotifier

    ok = EmailNotifier.send_order_confirmation(
        email='cliente@alimarket.com',
        order_id=42,
        total=123.45,
        items=['Laptop (x1)', 'Teclado (x2)'],
    )
    assert ok is True
    salida = capsys.readouterr().out
    assert 'CORREO ENVIADO' in salida
    assert 'Pedido ID: 42' in salida


def test_health_del_servicio():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'healthy'
    assert r.json()['service'] == 'notification-service'
