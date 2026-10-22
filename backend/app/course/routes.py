from flask import Blueprint, jsonify, request

from app.auth.access import login_required, roles_required
from app.common.roles import ADMIN
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
