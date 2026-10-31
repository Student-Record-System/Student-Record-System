"""Everything the reviews module needs from other modules goes through here."""
from app.grades import repository as grades_repository
from app.grades.service import APPROVED


def get_published_result(srn, course_code):
    """{"course_code", "published_at"} for an approved result, otherwise None.

    The grades module does not store an approval time yet, so the mark's
    updated_at is used. A mark is not edited after it is approved, so that
    value is the approval time. If a later feature edits approved marks,
    add an approved_at column to the grades model and read it here instead.
    """
    mark = grades_repository.get_mark(course_code, srn)
    if mark is None or mark.status != APPROVED:
        return None
    return {"course_code": mark.course_code, "published_at": mark.updated_at}