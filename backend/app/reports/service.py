import re

from app.common.clock import Clock
from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.roles import STUDENT
from app.reports import gateways
from app.reports.pdf import render_marksheet


def _parse_semester(raw):
    if raw is None or raw == "":
        return None  # no filter: every published semester
    try:
        semester = int(raw)
    except (TypeError, ValueError):
        raise ValidationError("semester must be a whole number between 1 and 8.")
    if not 1 <= semester <= 8:
        raise ValidationError("semester must be a whole number between 1 and 8.")
    return semester


def build_marksheet(requester, srn, semester_raw):
    """Return (pdf_bytes, filename) for a student's published results."""
    srn = srn.strip()
    if srn.lower() == "me":
        srn = requester.login_id
    # Ownership first, so a student cannot tell whether another SRN exists.
    if requester.role == STUDENT and requester.login_id != srn:
        raise ForbiddenError("You can only download your own mark sheet.")

    semester = _parse_semester(semester_raw)
    student = gateways.get_student(srn)  # raises NotFoundError if no profile

    results = gateways.get_published_results(student["srn"])
    if semester is not None:
        results = [r for r in results if r["semester"] == semester]
    if not results:
        raise NotFoundError("No published results found.", "ERR_NO_RESULTS")

    pdf = render_marksheet(
        student, results, gateways.get_gpa(student["srn"]),
        semester=semester, generated_at=Clock.now(),
    )
    safe_srn = re.sub(r"[^A-Za-z0-9_-]", "", student["srn"])
    suffix = f"_sem{semester}" if semester else ""
    return pdf, f"marksheet_{safe_srn}{suffix}.pdf"