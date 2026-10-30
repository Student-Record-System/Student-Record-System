from app.common.clock import Clock
from app.extensions import db


PENDING_APPROVAL = "Pending Approval"


class StudentMark(db.Model):
    __tablename__ = "student_marks"
    __table_args__ = (
        db.UniqueConstraint(
            "course_code",
            "srn",
            name="uq_student_mark_course_srn",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    course_code = db.Column(
        db.String(30),
        db.ForeignKey("courses.code"),
        nullable=False,
        index=True,
    )

    srn = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    internal_marks = db.Column(db.Float, nullable=False)
    end_semester_marks = db.Column(db.Float, nullable=False)

    status = db.Column(
        db.String(30),
        nullable=False,
        default=PENDING_APPROVAL,
    )

    submitted_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    submitted_at = db.Column(
        db.DateTime,
        nullable=False,
        default=Clock.now,
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=Clock.now,
        onupdate=Clock.now,
    )