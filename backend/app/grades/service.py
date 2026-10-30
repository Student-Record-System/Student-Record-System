from app.common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.roles import FACULTY
from app.course import repository as course_repository
from app.enrollment import repository as enrollment_repository
from app.enrollment.models import ENROLLED
from app.grades import repository
from app.grades.models import PENDING_APPROVAL, StudentMark


def _validate_marks(data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")

    srn = data.get("srn")
    if not isinstance(srn, str) or not srn.strip():
        raise ValidationError("srn is required.")

    values = {}
    for field in ("internal_marks", "end_semester_marks"):
        value = data.get(field)

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
        ):
            raise ValidationError(
                f"{field} must be a number between 0 and 100."
            )

        values[field] = float(value)

    values["srn"] = srn.strip()
    return values


def _as_dict(mark):
    return {
        "course_code": mark.course_code,
        "srn": mark.srn,
        "internal_marks": mark.internal_marks,
        "end_semester_marks": mark.end_semester_marks,
        "status": mark.status,
        "submitted_by": mark.submitted_by,
        "submitted_at": mark.submitted_at.isoformat(),
    }


def submit_marks(course_code, faculty, data):
    values = _validate_marks(data)
    course_code = course_code.strip().upper()

    course = course_repository.get_by_code(course_code)
    if course is None:
        raise NotFoundError("Course not found.")

    if faculty.role != FACULTY or course.faculty_id != faculty.id:
        raise ForbiddenError(
            "You can submit marks only for a course assigned to you."
        )

    enrollment = enrollment_repository.get_enrollment(
        values["srn"],
        course_code,
    )

    if enrollment is None or enrollment.status != ENROLLED:
        raise ConflictError(
            "The student is not currently enrolled in this course.",
            "ERR_STUDENT_NOT_ENROLLED",
        )

    if repository.get_mark(course_code, values["srn"]) is not None:
        raise ConflictError(
            "Marks have already been submitted for this student and course.",
            "ERR_MARKS_ALREADY_SUBMITTED",
        )

    mark = StudentMark(
        course_code=course_code,
        srn=values["srn"],
        internal_marks=values["internal_marks"],
        end_semester_marks=values["end_semester_marks"],
        status=PENDING_APPROVAL,
        submitted_by=faculty.id,
    )

    return _as_dict(repository.add_mark(mark))


APPROVED = "Approved"


def review_pending_marks():
    return [_as_dict(mark) for mark in repository.get_pending_marks()]


def approve_marks(course_code, srn):
    course_code = course_code.strip().upper()
    srn = srn.strip()

    mark = repository.get_mark(course_code, srn)
    if mark is None:
        raise NotFoundError("Marks not found.")

    if mark.status != PENDING_APPROVAL:
        raise ConflictError(
            "Only marks pending approval can be approved.",
            "ERR_MARKS_NOT_PENDING",
        )

    enrollment = enrollment_repository.get_enrollment(srn, course_code)
    if enrollment is None:
        raise NotFoundError("Student enrollment not found.")

    if enrollment.status != ENROLLED:
        raise ConflictError(
            "Only currently enrolled students can have results approved.",
            "ERR_ENROLLMENT_NOT_ACTIVE",
        )

    mark.status = APPROVED
    enrollment_repository.complete_enrollment(srn, course_code)
    return _as_dict(repository.save_mark(mark))


def student_results(student_srn):
    return [
        _as_dict(mark)
        for mark in repository.get_student_approved_marks(student_srn)
    ]

