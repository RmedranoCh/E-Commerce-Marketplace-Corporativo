import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _app_dir():
    return Path(__file__).resolve().parent


def _keys_dir():
    return Path(os.getenv('JWT_KEYS_DIR', '/app/db_data'))


def ensure_keys():
    """Garantiza que exista un par RSA (2048 bits) y sincroniza la clave pública.

    La clave privada se persiste en un volumen (por defecto /app/db_data), que
    nunca debe committearse. La clave pública se escribe tanto en el volumen
    (para que order-service y web-frontend la lean montando el mismo volumen)
    como dentro del paquete de la app para verificación local.
    """
    keys_dir = _keys_dir()
    try:
        keys_dir.mkdir(parents=True, exist_ok=True)
        writable = True
    except OSError:
        writable = False

    base_dir = keys_dir if writable else _app_dir()
    private_path = base_dir / "private_key.pem"
    public_path = base_dir / "public_key.pem"

    if not private_path.exists():
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    else:
        private_key = serialization.load_pem_private_key(
            private_path.read_bytes(), password=None
        )

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path.write_bytes(public_bytes)

    app_public = _app_dir() / "public_key.pem"
    app_public.write_bytes(public_bytes)

    return private_path
