"""Tests de demostración del auth-service (Flask + SQLite + JWT RS256).

Cubren el flujo completo: registro, login, verificación de token, límite
de intentos de login (rate limit) y endpoints de auditoría/salud.
"""


def test_health(client):
    r = client.get('/api/auth/health')
    assert r.status_code == 200
    assert r.json['status'] == 'healthy'
    assert r.json['service'] == 'auth-service'


def test_registro_comprador_exitoso(client):
    r = client.post('/api/auth/register', json={
        'username': 'comprador_uno',
        'email': 'comprador.uno@alimarket.com',
        'password': 'clave-segura-123',
        'role': 'comprador',
    })
    assert r.status_code == 201
    user = r.json['user']
    assert user['role'] == 'comprador'
    assert user['email'] == 'comprador.uno@alimarket.com'
    # La contraseña nunca debe exponerse en la respuesta.
    assert 'password' not in r.json


def test_registro_rechaza_email_invalido(client):
    r = client.post('/api/auth/register', json={
        'username': 'correo_malo',
        'email': 'esto-no-es-un-email',
        'password': 'clave-segura-123',
    })
    assert r.status_code == 400
    assert 'correo' in r.json['error'].lower()


def test_registro_rechaza_contrasena_corta(client):
    r = client.post('/api/auth/register', json={
        'username': 'usuario_corto',
        'email': 'corto@correo.com',
        'password': '123',
    })
    assert r.status_code == 400


def test_registro_rechaza_rol_invalido(client):
    r = client.post('/api/auth/register', json={
        'username': 'rol_malo',
        'email': 'rol.malo@correo.com',
        'password': 'clave-segura-123',
        'role': 'administrador',
    })
    assert r.status_code == 400


def test_registro_duplicado_rechazado(client):
    payload = {
        'username': 'duplicado',
        'email': 'duplicado@correo.com',
        'password': 'clave-segura-123',
    }
    assert client.post('/api/auth/register', json=payload).status_code == 201
    assert client.post('/api/auth/register', json=payload).status_code == 400


def test_flujo_completo_login_y_verificacion(client):
    client.post('/api/auth/register', json={
        'username': 'proveedor_alpha',
        'email': 'alpha@techmarket.com',
        'password': 'clave-segura-123',
        'role': 'proveedor',
    })
    login = client.post('/api/auth/login', json={
        'username': 'proveedor_alpha',
        'password': 'clave-segura-123',
    })
    assert login.status_code == 200
    token = login.json['access_token']
    assert login.json['user']['role'] == 'proveedor'

    verify = client.post('/api/auth/verify',
                         headers={'Authorization': f'Bearer {token}'})
    assert verify.status_code == 200
    assert verify.json['valid'] is True
    assert verify.json['role'] == 'proveedor'
    assert verify.json['email'] == 'alpha@techmarket.com'


def test_login_credenciales_invalidas(client):
    r = client.post('/api/auth/login', json={
        'username': 'fantasma',
        'password': 'clave-incorrecta',
    })
    assert r.status_code == 401


def test_verify_sin_token_o_invalido(client):
    assert client.post('/api/auth/verify').status_code == 401
    r = client.post('/api/auth/verify',
                    headers={'Authorization': 'Bearer token.falso.xyz'})
    assert r.status_code == 401


def test_login_rate_limit(client):
    # Solo se permiten 10 intentos por minuto (por IP).
    for _ in range(10):
        assert client.post('/api/auth/login', json={
            'username': 'spam',
            'password': 'clave-incorrecta',
        }).status_code == 401
    assert client.post('/api/auth/login', json={
        'username': 'spam',
        'password': 'clave-incorrecta',
    }).status_code == 429


def test_contador_de_proveedores(client):
    for i in range(2):
        client.post('/api/auth/register', json={
            'username': f'proveedor_{i}',
            'email': f'proveedor_{i}@techmarket.com',
            'password': 'clave-segura-123',
            'role': 'proveedor',
        })
    client.post('/api/auth/register', json={
        'username': 'comprador_solo',
        'email': 'comprador.solo@alimarket.com',
        'password': 'clave-segura-123',
        'role': 'comprador',
    })
    r = client.get('/api/auth/proveedores/count')
    assert r.status_code == 200
    assert r.json['count'] == 2
