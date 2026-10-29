from app.auth.models import User
from app.common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.roles import FACULTY
from app.course import repository
from app.course.models import Course
from app.enrollment.models import ENROLLED
from app.profile.models import StudentProfile


REQUIRED_FIELDS = ("code", "title", "credits", "semester", "department")


def _required_text(data, field):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required.")
    return value.strip()


def _validated_values(data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")

    values = {
        field: _required_text(data, field)
        for field in ("code", "title", "department")
    }

    credits = data.get("credits")
    semester = data.get("semester")

    if (
        isinstance(credits, bool)
        or not isinstance(credits, int)
        or not 1 <= credits <= 10
    ):
        raise ValidationError("credits must be an integer between 1 and 10.")

    if (
        isinstance(semester, bool)
        or not isinstance(semester, int)
        or not 1 <= semester <= 8
    ):
        raise ValidationError("semester must be an integer between 1 and 8.")

    values["credits"] = credits
    values["semester"] = semester
    return values


def _as_dict(course):
    return {
        "code": course.code,
        "title": course.title,
        "credits": course.credits,
        "semester": course.semester,
        "department": course.department,
    }


def create(data):
    values = _validated_values(data)
    values["code"] = values["code"].upper()

    if repository.get_by_code(values["code"]) is not None:
        raise ConflictError(
            "A course with this code already exists.",
            "ERR_DUPLICATE_COURSE",
        )

    return _as_dict(repository.add(Course(**values)))


def catalogue():
    return [_as_dict(course) for course in repository.list_all()]


def assign_faculty(course_code, faculty_login_id):
    if not isinstance(faculty_login_id, str) or not faculty_login_id.strip():
        raise ValidationError("faculty_login_id is required.")

    course = repository.get_by_code(course_code.upper())
    if course is None:
        raise NotFoundError("Course not found.")

    faculty = repository.get_user_by_login_id(faculty_login_id.strip())

    if faculty is None or faculty.role != FACULTY or not faculty.is_active:
        raise ValidationError("An active faculty account is required.")

    repository.assign_faculty(course, faculty)

    return {
        "course_code": course.code,
        "faculty_login_id": faculty.login_id,
    }


def roster(course_code, faculty):
    course = repository.get_by_code(course_code.upper())

    if course is None:
        raise NotFoundError("Course not found.")

    if course.faculty_id != faculty.id:
        raise ForbiddenError("You are not assigned to teach this course.")

    rows = repository.get_course_roster(course.code)

    students = [
        {
            "srn": profile.srn,
            "full_name": profile.full_name,
            "email": profile.email,
            "branch": profile.branch,
            "semester": profile.semester,
        }
        for enrollment, profile in rows
    ]

    return {
        "course_code": course.code,
        "course_title": course.title,
        "students": students,
    }