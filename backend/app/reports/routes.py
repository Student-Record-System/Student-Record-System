from flask import Blueprint, Response, request

from app.auth.access import current_user, roles_required
from app.common.roles import ADMIN, STUDENT
from app.reports import service

bp = Blueprint("reports", __name__, url_prefix="/api")


@bp.get("/students/<string:srn>/transcript")
@roles_required(STUDENT, ADMIN)
def download_marksheet(srn):
    pdf, filename = service.build_marksheet(
        current_user(), srn, request.args.get("semester")
    )
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )