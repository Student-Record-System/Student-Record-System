from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.common.clock import Clock
from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.common.settings import get_setting, set_setting
from app.enrollment import gateways, repository
from app.enrollment.models import ENROLLED, Enrollment
from app.extensions import db

WINDOW_START_KEY = "enrollment_window_start"
WINDOW_END_KEY = "enrollment_window_end"


def _course_code(value, field="course_code"):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required.")
    return value.strip().upper()


def _parse_datetime(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required.")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValidationError(
            f"{field} must be a date and time like 2026-10-26T09:00:00."
        ) from exc
    if parsed.tzinfo is not None:
        raise ValidationError(f"{field} must not include a time zone; times are UTC.")
    return parsed


def _as_dict(enrollment):
    return {
        "id": enrollment.id,
        "srn": enrollment.srn,
        "course_code": enrollment.course_code,
        "semester": enrollment.semester,
        "status": enrollment.status,
    }


# ---- enrollment window ----

def get_window():
    return {
        "start": get_setting(WINDOW_START_KEY),
        "end": get_setting(WINDOW_END_KEY),
    }


def set_window(data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    start = _parse_datetime(data.get("start"), "start")
    end = _parse_datetime(data.get("end"), "end")
    if start >= end:
        raise ValidationError("start must be earlier than end.")
    set_setting(WINDOW_START_KEY, start.isoformat())
    set_setting(WINDOW_END_KEY, end.isoformat())
    return get_window()


def _window_is_open():
    window = get_window()
    if window["start"] is None or window["end"] is None:
        return False  # not configured means closed
    now = Clock.now()
    return (
        datetime.fromisoformat(window["start"])
        <= now
        <= datetime.fromisoformat(window["end"])
    )


# ---- prerequisites ----

def set_prerequisites(course_code, data):
    code = _course_code(course_code, "course code")
    if not isinstance(data, dict) or not isinstance(data.get("prerequisites"), list):
        raise ValidationError("prerequisites must be a list of course codes.")
    if gateways.get_course(code) is None:
        raise NotFoundError("Course not found.")

    codes = []
    for item in data["prerequisites"]:
        prerequisite = _course_code(item, "prerequisite")
        if prerequisite == code:
            raise ValidationError("A course cannot be its own prerequisite.")
        if gateways.get_course(prerequisite) is None:
            raise NotFoundError(f"Prerequisite course {prerequisite} not found.")
        if prerequisite not in codes:
            codes.append(prerequisite)

    repository.replace_prerequisites(code, codes)
    return {"course_code": code, "prerequisites": sorted(codes)}


# ---- enrollment ----

def enroll(srn, data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    code = _course_code(data.get("course_code"))

    course = gateways.get_course(code)
    if course is None:
        raise NotFoundError("Course not found.")

    if not _window_is_open():
        raise ConflictError("The enrollment window is closed.", "ERR_WINDOW_CLOSED")

    student_semester = gateways.get_student_semester(srn)
    if course["semester"] != student_semester:
        raise ConflictError(
            "This course is not offered for your semester.", "ERR_WRONG_SEMESTER"
        )

    if repository.get_enrollment(srn, code) is not None:
        raise ConflictError(
            "You are already enrolled in this course.", "ERR_ALREADY_ENROLLED"
        )

    completed = repository.completed_course_codes(srn)
    missing = [c for c in repository.get_prerequisite_codes(code) if c not in completed]
    if missing:
        raise ConflictError(
            "Prerequisites not completed: " + ", ".join(missing) + ".",
            "ERR_PREREQ_NOT_MET",
        )

    # STU-F-023 (credit limit) and STU-F-054 (fee hold) add their checks here.

    enrollment = Enrollment(
        srn=srn, course_code=code, semester=course["semester"], status=ENROLLED
    )
    try:
        repository.add_enrollment(enrollment)
    except IntegrityError:  # two requests at the same moment
        db.session.rollback()
        raise ConflictError(
            "You are already enrolled in this course.", "ERR_ALREADY_ENROLLED"
        )
    return _as_dict(enrollment)