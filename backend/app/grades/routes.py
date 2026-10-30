from flask import Blueprint, jsonify, request

from app.auth.access import current_user, roles_required
from app.common.roles import FACULTY
from app.grades import service


bp = Blueprint("grades", __name__, url_prefix="/api")


@bp.post("/courses/<string:course_code>/marks")
@roles_required(FACULTY)
def submit_marks(course_code):
    result = service.submit_marks(
        course_code,
        current_user(),
        request.get_json(silent=True),
    )
    return jsonify(result), 201
