from datetime import timedelta

from app.common.audit import (
    archive_old_events,
    get_audit_events,
    record_event,
)
from app.common.clock import Clock
from app.common.models import AuditEvent, ArchivedAuditEvent
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


def test_archive_old_events_moves_events_older_than_five_years(app):
    with app.app_context():
        old_event = record_event(
            "GRADE_MODIFIED",
            login_id="FACULTY001",
            details={
                "previous_values": {"internal_marks": 70},
                "new_values": {"internal_marks": 85},
            },
        )

        old_event.created_at = Clock.now() - timedelta(days=6 * 365)

        db.session.flush()
        old_event_id = old_event.id

        db.session.commit()

        result = archive_old_events()

        assert result["archived_count"] == 1
        assert db.session.get(AuditEvent, old_event_id) is None

        archived = db.session.get(ArchivedAuditEvent, old_event_id)

        assert archived is not None
        assert archived.event_type == "GRADE_MODIFIED"
        assert archived.login_id == "FACULTY001"
        assert archived.details["previous_values"] == {
            "internal_marks": 70
        }
        assert archived.details["new_values"] == {
            "internal_marks": 85
        }


def test_archived_events_remain_retrievable(app):
    with app.app_context():
        event = record_event(
            "STUDENT_PROFILE_UPDATED",
            login_id="ADMIN001",
            details={
                "previous_values": {"phone": "111"},
                "new_values": {"phone": "222"},
            },
        )

        event.created_at = Clock.now() - timedelta(days=6 * 365)

        db.session.flush()
        event_id = event.id

        db.session.commit()

        archive_old_events()

        history = get_audit_events(
            event_types=["STUDENT_PROFILE_UPDATED"]
        )

        assert len(history) == 1
        assert history[0].id == event_id
        assert history[0].details["new_values"]["phone"] == "222"


def test_recent_events_are_not_archived(app):
    with app.app_context():
        event = record_event("RECENT_EVENT")
        db.session.commit()

        result = archive_old_events()

        assert result["archived_count"] == 0
        assert db.session.get(AuditEvent, event.id) is not None
        assert db.session.get(ArchivedAuditEvent, event.id) is None