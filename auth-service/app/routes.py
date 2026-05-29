import jwt
import logging
from flask import Blueprint, request, jsonify, current_app
from app.models import db, User
from app.utils.jwt_helper import generate_token
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "public_key.pem", "r") as f:
    PUBLIC_KEY = f.read()

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Faltan campos obligatorios"}), 400
    role = data.get('role', 'comprador')
    if role not in ['comprador', 'proveedor']:
        return jsonify({"error": "Rol de usuario no válido en el ecosistema"}), 400
        
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "El nombre de usuario ya está registrado"}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "El correo electrónico ya está registrado"}), 400
        
    new_user = User(username=data['username'], email=data['email'], role=role)
    new_user.set_password(data['password'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({
        "message": "Usuario registrado exitosamente", 
        "user": new_user.to_dict()
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username_or_email = data.get('username')
    password = data.get('password')
    
    if not username_or_email or not password:
        return jsonify({"error": "Usuario/Correo y contraseña requeridos"}), 400
        
    user = User.query.filter(
        (User.username == username_or_email) | (User.email == username_or_email)
    ).first()
    
    if user and user.check_password(password):
        token = generate_token(user.id, user.role)
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
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])
        return jsonify({
            "valid": True, 
            "user_id": payload['sub'],
            "role": payload.get('role', 'comprador')
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