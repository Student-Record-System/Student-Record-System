from app.extensions import db
from app.reviews.models import GradeReview


def get_review(srn, course_code):
    return db.session.execute(
        db.select(GradeReview).filter_by(srn=srn, course_code=course_code)
    ).scalar_one_or_none()


def add_review(review):
    """Saves the review and commits the whole transaction (including any audit event)."""
    db.session.add(review)
    db.session.commit()
    return review


def list_reviews(srn=None):
    query = db.select(GradeReview).order_by(
        GradeReview.created_at.desc(), GradeReview.id.desc()
    )
    if srn is not None:
        query = query.filter_by(srn=srn)
    return db.session.execute(query).scalars().all()