from flask import Blueprint, jsonify, request

from app.auth.access import current_user, login_required, roles_required
from app.common.roles import ADMIN, FACULTY
from app.course import service


bp = Blueprint("course", __name__, url_prefix="/api")


@bp.post("/courses")
@roles_required(ADMIN)
def create_course():
    return jsonify(service.create(request.get_json(silent=True))), 201


@bp.get("/courses")
@login_required
def get_catalogue():
    return jsonify(service.catalogue()), 200


@bp.put("/courses/<string:course_code>/faculty")
@roles_required(ADMIN)
def assign_course_faculty(course_code):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        from app.common.errors import ValidationError
        raise ValidationError("A JSON object is required.")

    result = service.assign_faculty(
        course_code,
        data.get("faculty_login_id"),
    )
    return jsonify(result), 200


@bp.get("/courses/<string:course_code>/roster")
@roles_required(FACULTY)
def get_course_roster(course_code):
    result = service.roster(course_code, current_user())
    return jsonify(result), 200