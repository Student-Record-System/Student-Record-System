from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app.common.audit import record_event
from app.common.clock import Clock
from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.common.roles import ADMIN
from app.common.settings import get_setting, set_setting
from app.extensions import db
from app.reviews import gateways, repository
from app.reviews.models import GradeReview

WINDOW_KEY = "grade_review_window_days"
DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 90
MAX_REASON_LENGTH = 1000


def _as_dict(review):
    return {
        "id": review.id,
        "srn": review.srn,
        "course_code": review.course_code,
        "reason": review.reason,
        "status": review.status,
        "created_at": review.created_at.isoformat(),
    }


# ---- review window setting ----

def _window_days():
    try:
        return int(get_setting(WINDOW_KEY, str(DEFAULT_WINDOW_DAYS)))
    except ValueError:
        return DEFAULT_WINDOW_DAYS


def get_window():
    return {"days": _window_days()}


def set_window(data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    days = data.get("days")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_WINDOW_DAYS:
        raise ValidationError(f"days must be a whole number between 1 and {MAX_WINDOW_DAYS}.")
    set_setting(WINDOW_KEY, str(days))
    return get_window()


# ---- review requests ----

def request_review(user, data):
    """A student asks for a published result to be reviewed (STU-F-044)."""
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    course_code = data.get("course_code")
    reason = data.get("reason")
    if not isinstance(course_code, str) or not course_code.strip():
        raise ValidationError("course_code is required.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("reason is required.")
    if len(reason.strip()) > MAX_REASON_LENGTH:
        raise ValidationError(f"reason must be at most {MAX_REASON_LENGTH} characters.")
    course_code = course_code.strip().upper()
    reason = reason.strip()
    srn = user.login_id  # always the logged-in student, never taken from the request

    result = gateways.get_published_result(srn, course_code)
    if result is None:
        # The same answer for "no such course", "not yours" and "not published yet".
        raise NotFoundError("No published result found for this course.", "ERR_NO_RESULT")

    deadline = result["published_at"] + timedelta(days=_window_days())
    if Clock.now() > deadline:
        raise ConflictError(
            "The review window for this result has closed.", "ERR_REVIEW_WINDOW_CLOSED"
        )

    if repository.get_review(srn, course_code) is not None:
        raise ConflictError(
            "You have already requested a review for this course.", "ERR_REVIEW_EXISTS"
        )

    review = GradeReview(srn=srn, course_code=course_code, reason=reason)
    record_event(
        "GRADE_REVIEW_REQUESTED",
        user_id=user.id,
        login_id=user.login_id,
        details={"course_code": course_code},
    )
    try:
        repository.add_review(review)
    except IntegrityError:  # two requests at the same moment
        db.session.rollback()
        raise ConflictError(
            "You have already requested a review for this course.", "ERR_REVIEW_EXISTS"
        )
    return _as_dict(review)


def list_reviews(user):
    """Students see their own requests; administrators see all of them."""
    srn = None if user.role == ADMIN else user.login_id
    return [_as_dict(review) for review in repository.list_reviews(srn)]