import os
import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PUBLIC_KEY_PATH = BASE_DIR / "public_key.pem"

PUBLIC_KEY = None
USE_ASYMMETRIC = None


def _public_key_path():
    env_path = os.getenv('JWT_PUBLIC_KEY_FILE', '')
    return env_path or str(DEFAULT_PUBLIC_KEY_PATH)


def _load_public_key():
    global PUBLIC_KEY, USE_ASYMMETRIC
    path = _public_key_path()
    try:
        with open(path, "r") as f:
            PUBLIC_KEY = f.read()
        USE_ASYMMETRIC = True
    except OSError:
        PUBLIC_KEY = os.getenv('JWT_SECRET_KEY', 'global-corporate-secret-key-2026')
        USE_ASYMMETRIC = False


_load_public_key()


class VirtualAuthenticatedUser:
    def __init__(self, user_id: int, role: str, email: str = None):
        self.id = user_id
        self.username = f"user_{user_id}"
        self.token_role = role
        self.email = email
    @property
    def is_authenticated(self) -> bool: return True
    @property
    def is_anonymous(self) -> bool: return False
    @property
    def is_staff(self) -> bool: return False
    def __str__(self): return self.username


class JWTSharedAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # Si la clave pública aún no estaba disponible (por ejemplo, porque el
        # volumen compartido se montó después del arranque), reinténtalo.
        if not USE_ASYMMETRIC:
            _load_public_key()

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.lower().startswith('bearer '):
            return None
        try:
            partes = auth_header.split(' ')
            if len(partes) != 2:
                raise AuthenticationFailed('Formato de encabezado Bearer inválido.')
            token = partes[1].strip()

            algoritmo = 'RS256' if USE_ASYMMETRIC else 'HS256'
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=[algoritmo])

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('El token corporativo ha expirado.')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Token JWT inválido, corrupto o mal firmado.')

        user = VirtualAuthenticatedUser(
            user_id=int(payload.get('sub')),
            role=payload.get('role', 'comprador'),
            email=payload.get('email')
        )
        return (user, token)
