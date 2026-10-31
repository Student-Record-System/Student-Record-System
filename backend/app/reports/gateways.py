"""Everything the reports module needs from other modules goes through here."""
from app.course import repository as course_repository
from app.grades import service as grades_service
from app.profile import service as profile_service


def get_student(srn):
    """The student's profile as a dict. Raises NotFoundError if there is none."""
    return profile_service.get(srn)


def get_published_results(srn):
    """Approved (published) results, sorted by semester then course code.
    Each result is the grades module's dict plus the course title."""
    results = []
    for result in grades_service.student_results(srn):
        course = course_repository.get_by_code(result["course_code"])
        results.append({
            **result,
            "course_title": course.title if course else result["course_code"],
        })
    return results


def get_gpa(srn):
    """{"semester_gpa": [{"semester", "gpa"}, ...], "cgpa": float}"""
    return grades_service.student_gpa(srn)