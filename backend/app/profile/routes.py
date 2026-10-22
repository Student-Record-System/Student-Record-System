from flask import Blueprint, jsonify, request

from app.auth.access import current_user, roles_required
from app.common.roles import ADMIN, STUDENT
from app.profile import service

bp = Blueprint("profile", __name__, url_prefix="/api")


@bp.get("/students/me")
@roles_required(STUDENT)
def get_own_student():
    return jsonify(service.get_for_student(current_user().login_id)), 200


@bp.patch("/students/me")
@roles_required(STUDENT)
def request_profile_changes():
    return jsonify(service.request_changes(
        current_user().login_id, current_user().id, request.get_json(silent=True)
    )), 202


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


@bp.post("/students/requests/<int:request_id>/approve")
@roles_required(ADMIN)
def approve_profile_change(request_id):
    return jsonify(service.approve_change(request_id)), 200


@bp.post("/students/requests/<int:request_id>/reject")
@roles_required(ADMIN)
def reject_profile_change(request_id):
    return jsonify(service.reject_change(request_id)), 200
