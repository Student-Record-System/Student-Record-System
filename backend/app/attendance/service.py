from datetime import date

from sqlalchemy.exc import IntegrityError

from app.attendance import repository
from app.attendance.models import ATTENDANCE_STATUSES, Attendance
from app.common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.course import repository as course_repository

def record_attendance(course_code, faculty, data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")

    course = course_repository.get_by_code(course_code.upper())

    if course is None:
        raise NotFoundError("Course not found.")

    if course.faculty_id != faculty.id:
        raise ForbiddenError("You are not assigned to teach this course.")

    date_value = data.get("attendance_date")

    if not isinstance(date_value, str) or not date_value.strip():
        raise ValidationError("attendance_date is required.")

    try:
        attendance_date = date.fromisoformat(date_value.strip())
    except ValueError:
        raise ValidationError(
            "attendance_date must be in YYYY-MM-DD format."
        )

    session = data.get("session")

    if not isinstance(session, str) or not session.strip():
        raise ValidationError("session is required.")

    session = session.strip()

    records = data.get("records")

    if not isinstance(records, list) or not records:
        raise ValidationError("records must be a non-empty list.")

    roster = course_repository.get_course_roster(course.code)
    enrolled_srns = {enrollment.srn for enrollment, profile in roster}

    seen_srns = set()
    attendance_records = []

    for record in records:
        if not isinstance(record, dict):
            raise ValidationError("Each attendance record must be a JSON object.")

        srn = record.get("srn")
        status = record.get("status")

        if not isinstance(srn, str) or not srn.strip():
            raise ValidationError("Every attendance record must include an SRN.")

        srn = srn.strip()

        if srn in seen_srns:
            raise ConflictError(
                f"Duplicate student {srn} in the attendance request.",
                "ERR_DUPLICATE_ATTENDANCE",
            )

        seen_srns.add(srn)

        if srn not in enrolled_srns:
            raise ConflictError(
                f"Student {srn} is not enrolled in this course.",
                "ERR_STUDENT_NOT_ENROLLED",
            )

        if status not in ATTENDANCE_STATUSES:
            raise ValidationError(
                f"Attendance status for {srn} must be Present or Absent."
            )

        if repository.get_attendance(
            srn, course.code, attendance_date, session
        ) is not None:
            raise ConflictError(
                f"Attendance already exists for student {srn} "
                f"in this session.",
                "ERR_DUPLICATE_ATTENDANCE",
            )

        attendance_records.append(
            Attendance(
                srn=srn,
                course_code=course.code,
                attendance_date=attendance_date,
                session=session,
                status=status,
                recorded_by=faculty.id,
            )
        )

    try:
        saved_records = repository.add_all(attendance_records)
    except IntegrityError:
        raise ConflictError(
            "Attendance already exists for one or more students in this session.",
            "ERR_DUPLICATE_ATTENDANCE",
        )

    return {
        "course_code": course.code,
        "attendance_date": attendance_date.isoformat(),
        "session": session,
        "records": [
            {
                "srn": item.srn,
                "status": item.status,
            }
            for item in saved_records
        ],
    }
