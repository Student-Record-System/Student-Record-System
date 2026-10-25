from app.extensions import db
from app.profile.models import StudentDocument


def get_by_id(document_id):
    return db.session.get(StudentDocument, document_id)


def get_by_profile_and_id(profile_id, document_id):
    return db.session.execute(
        db.select(StudentDocument).filter_by(
            profile_id=profile_id,
            id=document_id,
        )
    ).scalar_one_or_none()


def add(document):
    db.session.add(document)
    db.session.commit()
    return document


def delete(document):
    db.session.delete(document)
    db.session.commit()
