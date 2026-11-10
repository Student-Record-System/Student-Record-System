
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.attendance import repository
from app.attendance.models import ATTENDANCE_STATUSES, Attendance
from app.common.audit import record_event
from app.common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.notifications import get_notification_client
from app.common.settings import get_setting
from app.course import repository as course_repository
from app.profile import repository as profile_repository

ATTENDANCE_THRESHOLD_KEY = "attendance_minimum_percentage"
DEFAULT_ATTENDANCE_THRESHOLD = 75.0
ATTENDANCE_ALERT_KIND = "ATTENDANCE_BELOW_THRESHOLD"


def _attendance_threshold():
    configured = get_setting(
        ATTENDANCE_THRESHOLD_KEY,
        str(DEFAULT_ATTENDANCE_THRESHOLD),
    )
    try:
        threshold = float(configured)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "The configured attendance threshold must be a number between 0 and 100."
        ) from exc

    if not 0 <= threshold <= 100:
        raise ValidationError(
            "The configured attendance threshold must be a number between 0 and 100."
        )

    return threshold


def _notify_threshold_crossings(course, records, roster, threshold):
    profiles = {profile.srn: profile for _, profile in roster}
    notifications = get_notification_client()

    for record in records:
        present, total = repository.attendance_counts_for_student_course(
            record.srn,
            course.code,
        )
        previous_present = present - (record.status == "Present")
        previous_total = total - 1

        previous_percentage = _attendance_percentage(
            previous_present,
            previous_total,
        )
        current_percentage = _attendance_percentage(present, total)

        crossed_threshold = (
            current_percentage is not None
            and current_percentage < threshold
            and (
                previous_percentage is None
                or previous_percentage >= threshold
            )
        )

        if not crossed_threshold:
            continue

        profile = profiles[record.srn]

        notifications.send(
            recipient=profile.email,
            subject=f"Attendance below {threshold:g}% minimum",
            body=(
                f"Your attendance for {course.code} is "
                f"{current_percentage:.2f}%, below the configured "
                f"minimum of {threshold:g}%. "
                "Please take corrective action."
            ),
            kind=ATTENDANCE_ALERT_KIND,
        )


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
            raise ValidationError(
                "Each attendance record must be a JSON object."
            )

        srn = record.get("srn")
        status = record.get("status")

        if not isinstance(srn, str) or not srn.strip():
            raise ValidationError(
                "Every attendance record must include an SRN."
            )

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
            srn,
            course.code,
            attendance_date,
            session,
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
        threshold = _attendance_threshold()

        # Record an audit event for every attendance entry.
        for record in attendance_records:
            record_event(
                event_type="ATTENDANCE_CREATED",
                user_id=faculty.id,
                login_id=faculty.login_id,
                details={
                    "srn": record.srn,
                    "course_code": record.course_code,
                    "attendance_date": record.attendance_date.isoformat(),
                    "session": record.session,
                },
                previous_values=None,
                new_values={
                    "status": record.status,
                },
            )

        # Attendance records and audit events are committed together.
        saved_records = repository.add_all(attendance_records)

    except IntegrityError:
        raise ConflictError(
            "Attendance already exists for one or more students in this session.",
            "ERR_DUPLICATE_ATTENDANCE",
        )

    _notify_threshold_crossings(
        course,
        saved_records,
        roster,
        threshold,
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


def _attendance_percentage(present_sessions, total_sessions):
    if total_sessions == 0:
        return None

    return round((present_sessions / total_sessions) * 100, 2)


def _summary_record(srn, present_sessions, total_sessions):
    absent_sessions = total_sessions - present_sessions

    return {
        "srn": srn,
        "present_sessions": present_sessions,
        "absent_sessions": absent_sessions,
        "total_sessions": total_sessions,
        "attendance_percentage": _attendance_percentage(
            present_sessions,
            total_sessions,
        ),
    }


def course_attendance_summary(course_code, faculty):
    course = course_repository.get_by_code(course_code.upper())

    if course is None:
        raise NotFoundError("Course not found.")

    if course.faculty_id != faculty.id:
        raise ForbiddenError("You are not assigned to teach this course.")

    rows = repository.attendance_summary_for_course(course.code)

    return {
        "course_code": course.code,
        "students": [
            _summary_record(srn, present, total)
            for srn, present, total in rows
        ],
    }


def student_attendance_summary(srn):
    profile = profile_repository.get_by_srn(srn)

    if profile is None:
        raise NotFoundError("Student profile not found.")

    rows = repository.attendance_summary_for_student(srn)

    return {
        "srn": srn,
        "courses": [
            {
                "course_code": course_code,
                "present_sessions": present,
                "absent_sessions": total - present,
                "total_sessions": total,
                "attendance_percentage": _attendance_percentage(
                    present,
                    total,
                ),
            }
            for course_code, present, total in rows
        ],
    }


def student_attendance_records(srn):
    profile = profile_repository.get_by_srn(srn)

    if profile is None:
        raise NotFoundError("Student profile not found.")

    rows = repository.attendance_records_for_student(srn)

    courses = {}

    for course_code, attendance_date, session, status in rows:
        if course_code not in courses:
            courses[course_code] = []

        if attendance_date is not None:
            courses[course_code].append(
                {
                    "attendance_date": attendance_date.isoformat(),
                    "session": session,
                    "status": status,
                }
            )

    return {
        "srn": srn,
        "courses": [
            {
                "course_code": course_code,
                "records": records,
            }
            for course_code, records in courses.items()
        ],
    }
