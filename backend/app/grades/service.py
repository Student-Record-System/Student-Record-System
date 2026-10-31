
from app.common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.roles import FACULTY
from app.common.audit import record_event
from app.common.models import AuditEvent
from app.extensions import db
from app.course import repository as course_repository
from app.enrollment import repository as enrollment_repository
from app.enrollment.models import ENROLLED
from app.grades import repository
from app.grades.models import PENDING_APPROVAL, StudentMark


APPROVED = "Approved"


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

    db.session.add(mark)
    db.session.flush()

    record_event(
        event_type="GRADE_CREATED",
        user_id=faculty.id,
        login_id=faculty.login_id,
        details={
            "mark_id": mark.id,
            "course_code": course_code,
            "srn": values["srn"],
            "previous_values": None,
            "new_values": {
                "internal_marks": mark.internal_marks,
                "end_semester_marks": mark.end_semester_marks,
            },
        },
    )

    db.session.commit()

    return _as_dict(mark)


def modify_marks(course_code, srn, faculty, data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")

    values = _validate_marks({
        **data,
        "srn": srn,
    })

    course_code = course_code.strip().upper()

    course = course_repository.get_by_code(course_code)

    if course is None:
        raise NotFoundError("Course not found.")

    if faculty.role != FACULTY or course.faculty_id != faculty.id:
        raise ForbiddenError(
            "You can modify marks only for a course assigned to you."
        )

    mark = repository.get_mark(course_code, values["srn"])

    if mark is None:
        raise NotFoundError("Marks not found.")

    previous_values = {
        "internal_marks": mark.internal_marks,
        "end_semester_marks": mark.end_semester_marks,
    }

    new_values = {
        "internal_marks": values["internal_marks"],
        "end_semester_marks": values["end_semester_marks"],
    }

    mark.internal_marks = new_values["internal_marks"]
    mark.end_semester_marks = new_values["end_semester_marks"]

    record_event(
        event_type="GRADE_MODIFIED",
        user_id=faculty.id,
        login_id=faculty.login_id,
        details={
            "mark_id": mark.id,
            "course_code": course_code,
            "srn": values["srn"],
            "previous_values": previous_values,
            "new_values": new_values,
        },
    )

    db.session.commit()

    return _as_dict(mark)


def grade_history(course_code, srn):
    course_code = course_code.strip().upper()
    srn = srn.strip()

    mark = repository.get_mark(course_code, srn)

    if mark is None:
        raise NotFoundError("Marks not found.")

    events = db.session.execute(
        db.select(AuditEvent)
        .where(
            AuditEvent.event_type.in_([
                "GRADE_CREATED",
                "GRADE_MODIFIED",
            ])
        )
        .order_by(
            AuditEvent.created_at.asc(),
            AuditEvent.id.asc(),
        )
    ).scalars().all()

    history = []

    for event in events:
        details = event.details or {}

        if (
            details.get("course_code") == course_code
            and details.get("srn") == srn
        ):
            history.append({
                "faculty_id": event.user_id,
                "timestamp": event.created_at.isoformat(),
                "event_type": event.event_type,
                "previous_values": details.get("previous_values"),
                "new_values": details.get("new_values"),
            })

    return history


def _calculate_grade(internal_marks, end_semester_marks):
    total_marks = (internal_marks + end_semester_marks) / 2

    if total_marks >= 90:
        grade, grade_points = "S", 10
    elif total_marks >= 80:
        grade, grade_points = "A", 9
    elif total_marks >= 70:
        grade, grade_points = "B", 8
    elif total_marks >= 60:
        grade, grade_points = "C", 7
    elif total_marks >= 50:
        grade, grade_points = "D", 6
    elif total_marks >= 40:
        grade, grade_points = "E", 5
    else:
        grade, grade_points = "F", 0

    return round(total_marks, 2), grade, grade_points


def _result_as_dict(mark, course):
    total_marks, grade, grade_points = _calculate_grade(
        mark.internal_marks,
        mark.end_semester_marks,
    )

    result = _as_dict(mark)

    result.update({
        "total_marks": total_marks,
        "grade": grade,
        "grade_points": grade_points,
        "credits": course.credits,
        "semester": course.semester,
    })

    return result


def review_pending_marks():
    return [
        _as_dict(mark)
        for mark in repository.get_pending_marks()
    ]


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

    enrollment = enrollment_repository.get_enrollment(
        srn,
        course_code,
    )

    if enrollment is None:
        raise NotFoundError("Student enrollment not found.")

    if enrollment.status != ENROLLED:
        raise ConflictError(
            "Only currently enrolled students can have results approved.",
            "ERR_ENROLLMENT_NOT_ACTIVE",
        )

    mark.status = APPROVED

    enrollment_repository.complete_enrollment(
        srn,
        course_code,
    )

    return _as_dict(repository.save_mark(mark))


def student_results(student_srn):
    return [
        _result_as_dict(mark, course)
        for mark, course in repository.get_student_approved_results(
            student_srn
        )
    ]


def student_gpa(student_srn):
    approved_results = repository.get_student_approved_results(
        student_srn
    )

    semester_totals = {}
    overall_weighted_points = 0
    overall_credits = 0

    for mark, course in approved_results:
        _, _, grade_points = _calculate_grade(
            mark.internal_marks,
            mark.end_semester_marks,
        )

        credits = course.credits

        if course.semester not in semester_totals:
            semester_totals[course.semester] = {
                "weighted_points": 0,
                "credits": 0,
            }

        semester_totals[course.semester]["weighted_points"] += (
            grade_points * credits
        )

        semester_totals[course.semester]["credits"] += credits

        overall_weighted_points += grade_points * credits
        overall_credits += credits

    semester_gpa = []

    for semester in sorted(semester_totals):
        totals = semester_totals[semester]

        gpa = totals["weighted_points"] / totals["credits"]

        semester_gpa.append({
            "semester": semester,
            "gpa": round(gpa, 2),
        })

    cgpa = (
        overall_weighted_points / overall_credits
        if overall_credits > 0
        else 0.0
    )

    return {
        "semester_gpa": semester_gpa,
        "cgpa": round(cgpa, 2),
    }
