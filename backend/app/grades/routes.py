from flask import Blueprint, jsonify, request

from app.auth.access import current_user, roles_required
from app.common.roles import ADMIN, FACULTY, STUDENT
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


@bp.get("/admin/marks/pending")
@roles_required(ADMIN)
def review_pending_marks():
    return jsonify(service.review_pending_marks()), 200


@bp.post("/admin/marks/<string:course_code>/<string:srn>/approve")
@roles_required(ADMIN)
def approve_marks(course_code, srn):
    result = service.approve_marks(course_code, srn)
    return jsonify(result), 200


@bp.get("/student/results")
@roles_required(STUDENT)
def student_results():
    student = current_user()
    result = service.student_results(student.login_id)
    return jsonify(result), 200

@bp.get("/student/gpa")
@roles_required(STUDENT)
def student_gpa():
    student = current_user()
    result = service.student_gpa(student.login_id)
    return jsonify(result), 200

@bp.put("/courses/<string:course_code>/marks/<string:srn>")
@roles_required(FACULTY)
def modify_marks(course_code, srn):
    result = service.modify_marks(
        course_code,
        srn,
        current_user(),
        request.get_json(silent=True),
    )
    return jsonify(result), 200


@bp.get("/admin/grades/<string:course_code>/<string:srn>/history")
@roles_required(ADMIN)
def grade_history(course_code, srn):
    result = service.grade_history(course_code, srn)
    return jsonify(result), 200
