from flask import Blueprint, jsonify, request

from app.attendance import service
from app.auth.access import current_user, roles_required
from app.common.roles import FACULTY


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
