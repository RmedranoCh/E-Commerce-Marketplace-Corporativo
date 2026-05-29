import os
import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent 
PUBLIC_KEY_PATH = BASE_DIR / "public_key.pem"

try:
    with open(PUBLIC_KEY_PATH, "r") as f:
        PUBLIC_KEY = f.read()
    USE_ASYMMETRIC = True
except Exception:
    PUBLIC_KEY = os.getenv('JWT_SECRET_KEY', 'global-corporate-secret-key-2026')
    USE_ASYMMETRIC = False

class VirtualAuthenticatedUser:
    def __init__(self, user_id: int, role: str):
        self.id = user_id
        self.username = f"user_{user_id}"
        self.token_role = role
    @property
    def is_authenticated(self) -> bool: return True
    @property
    def is_anonymous(self) -> bool: return False
    @property
    def is_staff(self) -> bool: return False
    def __str__(self): return self.username

class JWTSharedAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
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
            role=payload.get('role', 'comprador')
        )
        return (user, token)