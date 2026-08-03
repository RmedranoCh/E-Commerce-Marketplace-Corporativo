"""Tests de demostración del web-frontend (BFF FastAPI).

Los servicios upstream (auth-service y order-service) se simulan con un
cliente HTTP falso para no depender de Docker ni de redes internas.
"""

import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import app.main as main


class RespuestaFake:
    def __init__(self, status_code, json_data=None, text=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text if text is not None else json.dumps(self._json)

    def json(self):
        return self._json


def _mock_httpx(monkeypatch, rutas, registro=None):
    class ClienteFake:
        def __init__(self, *args, **kwargs):
            self.llamadas = registro if registro is not None else []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def _respuesta(self, url):
            for fragmento, respuesta in rutas.items():
                if fragmento in url:
                    return respuesta
            return RespuestaFake(404, {'error': 'recurso no simulado'})

        async def get(self, url, **kwargs):
            self.llamadas.append(('GET', url))
            return self._respuesta(url)

        async def post(self, url, **kwargs):
            self.llamadas.append(('POST', url, kwargs))
            return self._respuesta(url)

        async def delete(self, url, **kwargs):
            self.llamadas.append(('DELETE', url))
            return self._respuesta(url)

    monkeypatch.setattr(main.httpx, 'AsyncClient', ClienteFake)
    return registro


def _generar_token(monkeypatch, role, sub=1, email=None):
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    publica = privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(main, 'PUBLIC_KEY', publica)
    now = datetime.now(timezone.utc)
    payload = {
        'sub': sub,
        'role': role,
        'email': email or f'usuario{sub}@correo.com',
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=2)).timestamp()),
    }
    return jwt.encode(payload, privada, algorithm='RS256')


def test_index_carga():
    client = TestClient(main.app)
    r = client.get('/')
    assert r.status_code == 200


def test_jwt_extraccion_roundtrip(monkeypatch):
    token = _generar_token(monkeypatch, 'proveedor', sub=42, email='p@techmarket.com')
    datos = main.extraer_datos_de_jwt(token)
    assert datos['sub'] == 42
    assert datos['role'] == 'proveedor'
    assert datos['email'] == 'p@techmarket.com'
    # Un token inválido nunca debe romper la request.
    assert main.extraer_datos_de_jwt('falso.token.xyz') == {}


def test_comprador_dashboard_renderiza_catalogo(monkeypatch):
    _mock_httpx(monkeypatch, {
        '/catalog/products/': RespuestaFake(200, [
            {'id': 1, 'name': 'Monitor OLED', 'is_offer': True,
             'offer_price': 249.99, 'price': 299.99, 'stock': 4,
             'imagen_urls': []},
            {'id': 2, 'name': 'Teclado Mecanico', 'is_offer': False,
             'price': 89.0, 'stock': 12, 'imagen_urls': []},
        ]),
    })
    token = _generar_token(monkeypatch, 'comprador', sub=9, email='cliente@alimarket.com')
    client = TestClient(main.app)
    client.cookies.set('access_token_comprador', token)
    r = client.get('/comprador')
    assert r.status_code == 200
    assert 'Monitor OLED' in r.text
    assert 'Teclado Mecanico' in r.text


def test_proveedor_panel_renderiza_inventario(monkeypatch):
    _mock_httpx(monkeypatch, {
        '/proveedores/count': RespuestaFake(200, {'count': 1}),
        '/catalog/products/': RespuestaFake(200, [
            {'id': 5, 'name': 'Router Industrial', 'is_offer': False,
             'price': 159.0, 'stock': 8, 'imagen_urls': []},
        ]),
    })
    token = _generar_token(monkeypatch, 'proveedor', sub=3, email='p@techmarket.com')
    client = TestClient(main.app)
    client.cookies.set('access_token_proveedor', token)
    r = client.get('/proveedor')
    assert r.status_code == 200
    assert 'Router Industrial' in r.text


def test_restock_rechaza_cantidad_invalida(monkeypatch):
    token = _generar_token(monkeypatch, 'proveedor', sub=3)
    client = TestClient(main.app, follow_redirects=False)
    client.cookies.set('access_token_proveedor', token)
    r = client.post('/catalog/restock/5', data={'quantity': '0'})
    assert r.status_code == 303
    assert 'ERROR' in r.headers['location']


def test_restock_exitoso(monkeypatch):
    _mock_httpx(monkeypatch, {'/restock/': RespuestaFake(200, {'id': 5})})
    token = _generar_token(monkeypatch, 'proveedor', sub=3)
    client = TestClient(main.app, follow_redirects=False)
    client.cookies.set('access_token_proveedor', token)
    r = client.post('/catalog/restock/5', data={'quantity': '10'})
    assert r.status_code == 303
    assert 'SUCCESS' in r.headers['location']


def test_restock_denegado_sin_sesion_proveedor(monkeypatch):
    client = TestClient(main.app, follow_redirects=False)
    r = client.post('/catalog/restock/5', data={'quantity': '10'})
    assert r.status_code == 303
    assert 'DENEGADO' in r.headers['location']


def test_add_product_valida_precio(monkeypatch):
    token = _generar_token(monkeypatch, 'proveedor', sub=3)
    client = TestClient(main.app, follow_redirects=False)
    client.cookies.set('access_token_proveedor', token)
    r = client.post('/catalog/add', data={
        'name': 'Producto Prueba',
        'price': '-1',
        'stock': '5',
    })
    assert r.status_code == 303
    assert 'ERROR' in r.headers['location']


def test_checkout_sin_autenticacion():
    client = TestClient(main.app)
    r = client.post('/comprador/checkout', json={'items': [{'product_id': 1, 'quantity': 1}]})
    assert r.status_code == 401


def test_checkout_rechaza_carrito_vacio(monkeypatch):
    token = _generar_token(monkeypatch, 'comprador', sub=9)
    client = TestClient(main.app)
    client.cookies.set('access_token_comprador', token)
    r = client.post('/comprador/checkout', json={'items': []})
    assert r.status_code == 400


def test_checkout_rechaza_cantidad_cero(monkeypatch):
    token = _generar_token(monkeypatch, 'comprador', sub=9)
    client = TestClient(main.app)
    client.cookies.set('access_token_comprador', token)
    r = client.post('/comprador/checkout',
                    json={'items': [{'product_id': 1, 'quantity': 0}]})
    assert r.status_code == 400


def test_checkout_exitoso_envia_email_del_jwt(monkeypatch):
    registro = []
    _mock_httpx(monkeypatch, {
        '/checkout/': RespuestaFake(201, {'id': 99}),
    }, registro=registro)
    token = _generar_token(monkeypatch, 'comprador', sub=9, email='cliente@alimarket.com')
    client = TestClient(main.app)
    client.cookies.set('access_token_comprador', token)
    r = client.post('/comprador/checkout',
                    json={'items': [{'product_id': 1, 'quantity': 2}]})
    assert r.status_code == 201
    assert r.json()['id'] == 99
    envio = [llamada for llamada in registro
             if llamada[0] == 'POST' and '/checkout/' in llamada[1]][0]
    payload = envio[2]['json']
    assert payload['email'] == 'cliente@alimarket.com'
    assert payload['items'] == [{'product_id': 1, 'quantity': 2}]


def test_catalogo_live_devuelve_lista(monkeypatch):
    _mock_httpx(monkeypatch, {
        '/catalog/products/': RespuestaFake(200, [{'id': 1, 'name': 'X'}]),
    })
    client = TestClient(main.app)
    r = client.get('/api/products/live')
    assert r.status_code == 200
    assert r.json()[0]['name'] == 'X'
