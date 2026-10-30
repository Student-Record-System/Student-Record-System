from flask import Blueprint, jsonify, request

from app.auth.access import current_user, roles_required
from app.common.roles import ADMIN, STUDENT
from app.profile import service

from flask import send_file
from flask_jwt_extended import get_jwt

from app.common.errors import ForbiddenError, NotFoundError
from app.common.filestore import FileStore, FileStoreError
from app.common.roles import ADMIN, STUDENT
from app.profile import document_service

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
    return jsonify(service.update(
        srn, request.get_json(silent=True), current_user()
    )), 200


@bp.get("/students/<string:srn>/history")
@roles_required(ADMIN, STUDENT)
def get_student_history(srn):
    user = current_user()
    if get_jwt().get("role") == STUDENT and user.login_id != srn:
        raise ForbiddenError("You do not have permission to view this history.")
    return jsonify({"history": service.history(srn)}), 200


@bp.post("/students/requests/<int:request_id>/approve")
@roles_required(ADMIN)
def approve_profile_change(request_id):
    return jsonify(service.approve_change(request_id, current_user())), 200


@bp.post("/students/requests/<int:request_id>/reject")
@roles_required(ADMIN)
def reject_profile_change(request_id):
    return jsonify(service.reject_change(request_id)), 200


@bp.post("/students/<string:srn>/documents")
@roles_required(ADMIN)
def upload_student_document(srn):
    uploaded_file = request.files.get("file")
    result = document_service.upload_document(srn, uploaded_file)
    return jsonify(result), 201


@bp.get("/students/<string:srn>/documents/<int:document_id>")
@roles_required(ADMIN, STUDENT)
def get_student_document(srn, document_id):
    user = current_user()
    role = get_jwt().get("role")

    document = document_service.get_document(
        srn, document_id, user, role
    )

    try:
        file_handle = FileStore().open(document.stored_name)
    except FileNotFoundError as exc:
        raise NotFoundError("Stored document not found.") from exc
    except FileStoreError as exc:
        raise NotFoundError("Stored document not found.") from exc

    return send_file(
        file_handle,
        mimetype=document.content_type,
        as_attachment=True,
        download_name=document.original_name,
    )
