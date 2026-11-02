from app.common.clock import Clock
from app.extensions import db

PRESENT = "Present"
ABSENT = "Absent"
ATTENDANCE_STATUSES = (PRESENT, ABSENT)


class Attendance(db.Model):
    __tablename__ = "attendance_records"
    __table_args__ = (
        db.UniqueConstraint(
            "srn",
            "course_code",
            "attendance_date",
            "session",
            name="uq_attendance_student_course_date_session",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    srn = db.Column(
        db.String(50),
        db.ForeignKey("student_profiles.srn"),
        nullable=False,
        index=True,
    )

    course_code = db.Column(
        db.String(30),
        db.ForeignKey("courses.code"),
        nullable=False,
        index=True,
    )

    attendance_date = db.Column(db.Date, nullable=False)
    session = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(10), nullable=False)

    recorded_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=Clock.now,
    )
