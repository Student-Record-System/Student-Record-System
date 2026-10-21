from flask import Blueprint, jsonify, request

from app.auth.access import roles_required
from app.common.roles import ADMIN
from app.profile import service

bp = Blueprint("profile", __name__, url_prefix="/api")


@bp.post("/students")
@roles_required(ADMIN)
def create_student():
    return jsonify(service.create(request.get_json(silent=True))), 201


@bp.get("/students/<string:srn>")
@roles_required(ADMIN)
def get_student(srn):
    return jsonify(service.get(srn)), 200


@bp.put("/students/<string:srn>")
@roles_required(ADMIN)
def update_student(srn):
    return jsonify(service.update(srn, request.get_json(silent=True))), 200
