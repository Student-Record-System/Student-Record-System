from app.common.clock import Clock
from app.extensions import db

ENROLLED = "Enrolled"
COMPLETED = "Completed"  # set later, when results are published (STU-F-041)


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("srn", "course_code", name="uq_enrollment_srn_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    srn = db.Column(db.String(50), nullable=False, index=True)
    course_code = db.Column(db.String(30), nullable=False, index=True)
    semester = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ENROLLED)
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)


class CoursePrerequisite(db.Model):
    __tablename__ = "course_prerequisites"
    __table_args__ = (
        db.UniqueConstraint(
            "course_code", "prerequisite_code", name="uq_course_prerequisite"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(30), nullable=False, index=True)
    prerequisite_code = db.Column(db.String(30), nullable=False)