from app.extensions import db
from app.profile.models import StudentProfile


def get_by_srn(srn):
    return db.session.execute(
        db.select(StudentProfile).filter_by(srn=srn)
    ).scalar_one_or_none()


def add(profile):
    db.session.add(profile)
    db.session.commit()
    return profile


def save(profile):
    db.session.commit()
    return profile
