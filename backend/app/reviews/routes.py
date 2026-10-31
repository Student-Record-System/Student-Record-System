from flask import Blueprint, jsonify, request

from app.auth.access import current_user, roles_required
from app.common.roles import ADMIN, STUDENT
from app.reviews import service

bp = Blueprint("reviews", __name__, url_prefix="/api")


@bp.post("/grade-reviews")
@roles_required(STUDENT)
def request_review():
    return jsonify(service.request_review(current_user(), request.get_json(silent=True))), 201


@bp.get("/grade-reviews")
@roles_required(STUDENT, ADMIN)
def list_reviews():
    return jsonify(service.list_reviews(current_user())), 200


@bp.get("/config/review-window")
@roles_required(ADMIN)
def get_window():
    return jsonify(service.get_window()), 200


@bp.put("/config/review-window")
@roles_required(ADMIN)
def set_window():
    return jsonify(service.set_window(request.get_json(silent=True))), 200