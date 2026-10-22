from app.common.errors import ConflictError, ValidationError
from app.course import repository
from app.course.models import Course

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
    if isinstance(credits, bool) or not isinstance(credits, int) or not 1 <= credits <= 10:
        raise ValidationError("credits must be an integer between 1 and 10.")
    if isinstance(semester, bool) or not isinstance(semester, int) or not 1 <= semester <= 8:
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
        raise ConflictError("A course with this code already exists.", "ERR_DUPLICATE_COURSE")
    return _as_dict(repository.add(Course(**values)))


def catalogue():
    return [_as_dict(course) for course in repository.list_all()]
