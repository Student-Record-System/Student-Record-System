from app.common.clock import Clock
from app.extensions import db

PENDING_REVIEW = "Pending Review"


class GradeReview(db.Model):
    """A student's request to have one published result looked at again."""
    __tablename__ = "grade_reviews"
    __table_args__ = (
        db.UniqueConstraint("srn", "course_code", name="uq_grade_review_srn_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    srn = db.Column(db.String(50), nullable=False, index=True)
    course_code = db.Column(db.String(30), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=PENDING_REVIEW)
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)