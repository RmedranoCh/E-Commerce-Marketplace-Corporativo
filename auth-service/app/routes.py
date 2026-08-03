import logging
import re

import jwt
from flask import Blueprint, request, jsonify

from app.models import db, User
from app.rate_limiter import rate_limiter
from app.utils.jwt_helper import generate_token, get_public_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = str(data.get('username') or '').strip()
    email = str(data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role', 'comprador')

    if not username or not email or not password:
        return jsonify({"error": "Faltan campos obligatorios"}), 400
    if len(username) < 3 or len(username) > 64:
        return jsonify({"error": "El nombre de usuario debe tener entre 3 y 64 caracteres"}), 400
    if len(password) < 6 or len(password) > 128:
        return jsonify({"error": "La contraseña debe tener entre 6 y 128 caracteres"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Formato de correo electrónico inválido"}), 400
    if role not in ['comprador', 'proveedor']:
        return jsonify({"error": "Rol de usuario no válido en el ecosistema"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "El nombre de usuario ya está registrado"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "El correo electrónico ya está registrado"}), 400

    new_user = User(username=username, email=email, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({
        "message": "Usuario registrado exitosamente",
        "user": new_user.to_dict()
    }), 201


@auth_bp.route('/login', methods=['POST'])
@rate_limiter.limit(max_hits=10, window_seconds=60)
def login():
    data = request.get_json() or {}
    username_or_email = data.get('username')
    password = data.get('password')

    if not username_or_email or not password:
        return jsonify({"error": "Usuario/Correo y contraseña requeridos"}), 400

    user = User.query.filter(
        (User.username == username_or_email) | (User.email == username_or_email.lower())
    ).first()

    if user and user.check_password(password):
        token = generate_token(user.id, user.role, user.email)
        return jsonify({
            "access_token": token,
            "token_type": "Bearer",
            "user": user.to_dict()
        }), 200

    return jsonify({"error": "Credenciales inválidas corporativas"}), 401


@auth_bp.route('/verify', methods=['POST'])
def verify():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Formato de token inválido o ausente"}), 401
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, get_public_key(), algorithms=['RS256'])
        return jsonify({
            "valid": True,
            "user_id": payload['sub'],
            "role": payload.get('role', 'comprador'),
            "email": payload.get('email')
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "El token ha expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido o firma corrupta"}), 401


@auth_bp.route('/proveedores/count', methods=['GET'])
def count_proveedores():
    try:
        count = User.query.filter_by(role='proveedor').count()
        return jsonify({"count": count}), 200
    except Exception as e:
        logger.error(f"[AUDITORÍA FALLIDA] Error en consulta de proveedores: {str(e)}")
        return jsonify({"error": "Fallo al procesar la solicitud de auditoría interna."}), 500


@auth_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "auth-service"}), 200
