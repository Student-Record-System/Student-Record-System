from app.common.clock import Clock
from app.common.models import AuditEvent, ArchivedAuditEvent
from app.extensions import db


_UNSET = object()


def record_event(
    event_type,
    user_id=None,
    login_id=None,
    details=None,
    profile_id=None,
    previous_values=_UNSET,
    new_values=_UNSET,
):
    """Add an audit event to the current database transaction.

    The caller is responsible for committing the transaction.
    Existing callers remain backward-compatible.
    """
    event_details = dict(details or {})

    if previous_values is not _UNSET:
        event_details["previous_values"] = previous_values

    if new_values is not _UNSET:
        event_details["new_values"] = new_values

    event = AuditEvent(
        event_type=event_type,
        user_id=user_id,
        profile_id=profile_id,
        login_id=login_id,
        details=event_details,
        created_at=Clock.now(),
    )

    db.session.add(event)
    return event


def get_audit_events(event_types=None, user_id=None, profile_id=None):
    """Retrieve matching events from both active and archived storage."""
    active_query = db.select(AuditEvent)
    archived_query = db.select(ArchivedAuditEvent)

    if event_types is not None:
        active_query = active_query.where(
            AuditEvent.event_type.in_(event_types)
        )
        archived_query = archived_query.where(
            ArchivedAuditEvent.event_type.in_(event_types)
        )

    if user_id is not None:
        active_query = active_query.where(AuditEvent.user_id == user_id)
        archived_query = archived_query.where(
            ArchivedAuditEvent.user_id == user_id
        )

    if profile_id is not None:
        active_query = active_query.where(
            AuditEvent.profile_id == profile_id
        )
        archived_query = archived_query.where(
            ArchivedAuditEvent.profile_id == profile_id
        )

    active_events = db.session.execute(active_query).scalars().all()
    archived_events = db.session.execute(archived_query).scalars().all()

    return sorted(
        active_events + archived_events,
        key=lambda event: (event.created_at, event.id),
    )


def archive_old_events():
    """Move audit events older than five years into archive storage."""
    now = Clock.now()

    try:
        cutoff = now.replace(year=now.year - 5)
    except ValueError:
        # Handle February 29 when the target year is not a leap year.
        cutoff = now.replace(year=now.year - 5, day=28)

    old_events = db.session.execute(
        db.select(AuditEvent).where(AuditEvent.created_at < cutoff)
    ).scalars().all()

    archived_count = 0

    try:
        for event in old_events:
            archived_event = ArchivedAuditEvent(
                id=event.id,
                event_type=event.event_type,
                user_id=event.user_id,
                profile_id=event.profile_id,
                login_id=event.login_id,
                details=event.details,
                created_at=event.created_at,
                archived_at=now,
            )

            db.session.add(archived_event)
            db.session.flush()
            db.session.delete(event)
            archived_count += 1

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return {
        "archived_count": archived_count,
        "cutoff": cutoff.isoformat(),
    }