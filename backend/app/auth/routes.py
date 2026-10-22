from flask import Blueprint, jsonify, request

from app.auth import service
from app.auth.access import roles_required
from app.common.errors import ValidationError
from app.common.roles import ADMIN

bp = Blueprint("auth", __name__, url_prefix="/api")


def _text(data, key):
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    login_id = data.get("login_id")
    password = data.get("password")
    if (not isinstance(login_id, str) or not isinstance(password, str)
            or not login_id.strip() or not password):
        raise ValidationError("login_id and password are required.")
    return jsonify(service.login(login_id.strip(), password)), 200


@bp.post("/users")
@roles_required(ADMIN)
def create_user():
    data = request.get_json(silent=True) or {}
    login_id, email, role = _text(data, "login_id"), _text(data, "email"), _text(data, "role")
    if not (login_id and email and role):
        raise ValidationError("login_id, email and role are required.")
    user = service.create_user(login_id, email, role)
    return jsonify({
        "id": user.id, "login_id": user.login_id,
        "email": user.email, "role": user.role,
    }), 201