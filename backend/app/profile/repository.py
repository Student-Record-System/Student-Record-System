from app.extensions import db
from app.common.models import AuditEvent
from app.profile.models import ProfileChangeRequest, StudentProfile


def get_by_srn(srn):
    return db.session.execute(
        db.select(StudentProfile).filter_by(srn=srn)
    ).scalar_one_or_none()


def get_by_id(profile_id):
    return db.session.get(StudentProfile, profile_id)


def add(profile):
    db.session.add(profile)
    db.session.commit()
    return profile


def save(profile):
    db.session.commit()
    return profile


def get_history(profile_id):
    return db.session.execute(
        db.select(AuditEvent)
        .filter_by(profile_id=profile_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).scalars().all()


def get_pending_request(profile_id):
    return db.session.execute(
        db.select(ProfileChangeRequest).filter_by(
            profile_id=profile_id, status="Pending Verification"
        )
    ).scalar_one_or_none()


def get_change_request(request_id):
    return db.session.get(ProfileChangeRequest, request_id)


def add_change_request(change_request):
    db.session.add(change_request)
    db.session.commit()
    return change_request


def save_change_request(change_request):
    db.session.commit()
    return change_request
