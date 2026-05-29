from pathlib import Path
from datetime import datetime, timezone, timedelta
import jwt

BASE_DIR = Path(__file__).resolve().parent.parent

with open(BASE_DIR / "private_key.pem", "r") as f:
    PRIVATE_KEY = f.read()

def generate_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'exp': int((now + timedelta(hours=2)).timestamp()),
        'iat': int(now.timestamp()),
        'sub': user_id,
        'role': role
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm='RS256')