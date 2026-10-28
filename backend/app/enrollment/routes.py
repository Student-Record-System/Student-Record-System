from flask import Blueprint, jsonify, request

from app.auth.access import current_user, roles_required
from app.common.roles import ADMIN, STUDENT
from app.enrollment import service

bp = Blueprint("enrollment", __name__, url_prefix="/api")


@bp.post("/enrollments")
@roles_required(STUDENT)
def enroll():
    result = service.enroll(current_user().login_id, request.get_json(silent=True))
    return jsonify(result), 201


@bp.get("/config/enrollment-window")
@roles_required(ADMIN)
def get_window():
    return jsonify(service.get_window()), 200


@bp.put("/config/enrollment-window")
@roles_required(ADMIN)
def set_window():
    return jsonify(service.set_window(request.get_json(silent=True))), 200


@bp.put("/courses/<string:course_code>/prerequisites")
@roles_required(ADMIN)
def set_prerequisites(course_code):
    return jsonify(
        service.set_prerequisites(course_code, request.get_json(silent=True))
    ), 200


@bp.get("/enrollments/current")
@roles_required(STUDENT)
def current_enrollments():
    result = service.current_semester_courses(current_user().login_id)
    return jsonify(result), 200
