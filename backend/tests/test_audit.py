from app.common.audit import record_event
from app.common.models import AuditEvent
from app.extensions import db


def test_record_event_adds_event_to_database(app):
    with app.app_context():
        event = record_event(
            "ACCOUNT_LOCKED",
            login_id="PES2UG24CS001",
            details={"failed_attempts": 5, "lockout_minutes": 15},
        )
        db.session.commit()

        saved = db.session.get(AuditEvent, event.id)

        assert saved is not None
        assert saved.event_type == "ACCOUNT_LOCKED"
        assert saved.login_id == "PES2UG24CS001"
        assert saved.details["failed_attempts"] == 5
        assert saved.details["lockout_minutes"] == 15


def test_record_event_supports_events_without_user(app):
    with app.app_context():
        event = record_event("AUTHENTICATION_FAILURE")
        db.session.commit()

        saved = db.session.get(AuditEvent, event.id)

        assert saved is not None
        assert saved.user_id is None
        assert saved.login_id is None
        assert saved.details == {}
