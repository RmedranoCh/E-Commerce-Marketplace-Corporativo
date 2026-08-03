"""Tests de demostración de la autenticación JWT compartida del order-service.

Se generan pares RSA efímeros en memoria para verificar que la autenticación
RS256 acepta tokens válidos y rechaza los corruptos o expirados.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from rest_framework.exceptions import AuthenticationFailed

import core.authentication as auth


@pytest.fixture()
def par_de_llaves():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    publica_pem = privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return privada, publica_pem


@pytest.fixture()
def claves_de_prueba(monkeypatch, par_de_llaves):
    monkeypatch.setattr(auth, 'PUBLIC_KEY', par_de_llaves[1])
    monkeypatch.setattr(auth, 'USE_ASYMMETRIC', True)
    return par_de_llaves


def _token(privada, payload):
    return jwt.encode(payload, privada, algorithm='RS256')


def _request_bearer(token=None):
    headers = {} if token is None else {'Authorization': f'Bearer {token}'}
    return SimpleNamespace(headers=headers)


def test_token_valido_rs256(claves_de_prueba):
    privada, _ = claves_de_prueba
    exp = datetime.now(timezone.utc) + timedelta(hours=2)
    token = _token(privada, {
        'sub': 7, 'role': 'proveedor', 'email': 'proveedor@techmarket.com',
        'iat': datetime.now(timezone.utc).timestamp(),
        'exp': exp.timestamp(),
    })
    usuario, _ = auth.JWTSharedAuthentication().authenticate(_request_bearer(token))
    assert usuario.id == 7
    assert usuario.token_role == 'proveedor'
    assert usuario.email == 'proveedor@techmarket.com'
    assert usuario.is_authenticated is True


def test_sin_encabezado_devuelve_none():
    assert auth.JWTSharedAuthentication().authenticate(_request_bearer(None)) is None


def test_formato_bearer_invalido(claves_de_prueba):
    # 'Bearer' sin espacio se trata como petición anónima.
    assert auth.JWTSharedAuthentication().authenticate(
        SimpleNamespace(headers={'Authorization': 'Bearer'})) is None
    # 'Bearer ' con token vacío sí es un formato inválido.
    with pytest.raises(AuthenticationFailed):
        auth.JWTSharedAuthentication().authenticate(
            SimpleNamespace(headers={'Authorization': 'Bearer '}))


def test_token_corrupto_rechazado(claves_de_prueba):
    privada, _ = claves_de_prueba
    token = _token(privada, {
        'sub': 1, 'role': 'comprador',
        'iat': datetime.now(timezone.utc).timestamp(),
        'exp': (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
    })
    token_corrupto = token[:-4] + 'AAAA'
    with pytest.raises(AuthenticationFailed):
        auth.JWTSharedAuthentication().authenticate(_request_bearer(token_corrupto))


def test_token_expirado_rechazado(claves_de_prueba):
    privada, _ = claves_de_prueba
    token = _token(privada, {
        'sub': 1, 'role': 'comprador',
        'iat': (datetime.now(timezone.utc) - timedelta(hours=3)).timestamp(),
        'exp': (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp(),
    })
    with pytest.raises(AuthenticationFailed) as exc:
        auth.JWTSharedAuthentication().authenticate(_request_bearer(token))
    assert 'expirado' in str(exc.value)


def test_token_firmado_con_otra_clave_rechazado(claves_de_prueba):
    otra_privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _token(otra_privada, {
        'sub': 1, 'role': 'comprador',
        'iat': datetime.now(timezone.utc).timestamp(),
        'exp': (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
    })
    with pytest.raises(AuthenticationFailed):
        auth.JWTSharedAuthentication().authenticate(_request_bearer(token))
