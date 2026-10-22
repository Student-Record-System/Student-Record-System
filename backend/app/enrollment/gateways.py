from app.course import repository as course_repository
from app.profile import service as profile_service


def get_course(course_code):
    """Return {"code", "credits", "semester"} for a course, or None."""
    course = course_repository.get_by_code(course_code)
    if course is None:
        return None
    return {
        "code": course.code,
        "credits": course.credits,
        "semester": course.semester,
    }


def get_student_semester(srn):
    """The student's semester, from their profile (STU-F-010).
    Raises NotFoundError if the student has no profile."""
    return profile_service.get(srn)["semester"]