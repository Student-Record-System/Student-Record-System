from flask import Blueprint, jsonify, request

from app.auth.access import roles_required
from app.common.audit import get_audit_events
from app.common.errors import ValidationError
from app.common.roles import ADMIN

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _optional_positive_int(name):
    value = request.args.get(name)
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValidationError(f"{name} must be an integer.") from exc
    if parsed < 1:
        raise ValidationError(f"{name} must be a positive integer.")
    return parsed


@bp.get("/audit-events")
@roles_required(ADMIN)
def list_audit_events():
    event_type = request.args.get("event_type")
    event_types = [event_type.strip()] if event_type and event_type.strip() else None
    events = get_audit_events(
        event_types=event_types,
        user_id=_optional_positive_int("user_id"),
        profile_id=_optional_positive_int("profile_id"),
    )
    return jsonify({
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "profile_id": event.profile_id,
                "login_id": event.login_id,
                "details": event.details,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
    }), 200
