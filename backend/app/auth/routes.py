from flask import Blueprint, jsonify, request

from app.auth import service
from app.common.errors import ValidationError

bp = Blueprint("auth", __name__, url_prefix="/api")


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    login_id = data.get("login_id")
    password = data.get("password")
    if (not isinstance(login_id, str) or not isinstance(password, str)
            or not login_id.strip() or not password):
        raise ValidationError("login_id and password are required.")
    return jsonify(service.login(login_id.strip(), password)), 200