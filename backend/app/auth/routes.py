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


@bp.post("/auth/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email")

    if not isinstance(email, str) or not email.strip():
        raise ValidationError("A valid email address is required.")

    return jsonify(service.request_password_reset(email)), 200


@bp.post("/auth/reset-password")
def reset_forgotten_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    otp = data.get("otp")
    new_password = data.get("new_password")

    if not isinstance(email, str) or not email.strip():
        raise ValidationError("A valid email address is required.")

    if not isinstance(otp, str) or not otp.isdigit() or len(otp) != 6:
        raise ValidationError("OTP must be a 6-digit code.")

    if not isinstance(new_password, str) or len(new_password) < 8:
        raise ValidationError("New password must contain at least 8 characters.")

    return jsonify(
        service.reset_password(email, otp, new_password)
    ), 200
