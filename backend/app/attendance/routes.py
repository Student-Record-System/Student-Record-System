from flask import Blueprint, jsonify, request

from app.attendance import service
from app.auth.access import current_user, roles_required
from app.common.roles import FACULTY, STUDENT


bp = Blueprint("attendance", __name__, url_prefix="/api")


@bp.post("/courses/<string:course_code>/attendance")
@roles_required(FACULTY)
def record_course_attendance(course_code):
    result = service.record_attendance(
        course_code,
        current_user(),
        request.get_json(silent=True),
    )
    return jsonify(result), 201

@bp.get("/courses/<string:course_code>/attendance/summary")
@roles_required(FACULTY)
def get_course_attendance_summary(course_code):
    result = service.course_attendance_summary(
        course_code,
        current_user(),
    )
    return jsonify(result), 200


@bp.get("/students/me/attendance")
@roles_required(STUDENT)
def get_my_attendance_summary():
    result = service.student_attendance_summary(
        current_user().login_id
    )
    return jsonify(result), 200