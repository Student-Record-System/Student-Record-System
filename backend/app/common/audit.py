from app.common.clock import Clock
from app.common.models import AuditEvent
from app.extensions import db


def record_event(
    event_type, user_id=None, login_id=None, details=None, profile_id=None
):
    """Add an audit event to the current database transaction.

    The caller is responsible for committing the transaction.
    """
    event = AuditEvent(
        event_type=event_type,
        user_id=user_id,
        profile_id=profile_id,
        login_id=login_id,
        details=details or {},
        created_at=Clock.now(),
    )
    db.session.add(event)
    return event
