from datetime import datetime, timezone, timedelta

import jwt

from app.key_manager import ensure_keys


def get_private_key():
    return ensure_keys().read_bytes()


def get_public_key():
    return (ensure_keys().parent / "public_key.pem").read_bytes()


def generate_token(user_id: int, role: str, email: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'exp': int((now + timedelta(hours=2)).timestamp()),
        'iat': int(now.timestamp()),
        'sub': user_id,
        'role': role,
        'email': email,
    }
    return jwt.encode(payload, get_private_key(), algorithm='RS256')
