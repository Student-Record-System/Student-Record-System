from datetime import date

from app.common.clock import Clock
from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.profile import repository
from app.profile.models import ProfileChangeRequest, StudentProfile

REQUIRED_FIELDS = (
    "srn",
    "full_name",
    "email",
    "phone",
    "date_of_birth",
    "gender",
    "program",
    "branch",
    "semester",
)
PERMITTED_FIELDS = (
    "phone",
    "address",
    "emergency_contact_name",
    "emergency_contact_phone",
)


def _required_text(data, field):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required.")
    return value.strip()


def _parse_date(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("date_of_birth is required.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValidationError("date_of_birth must use YYYY-MM-DD format.") from exc


def _parse_semester(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8:
        raise ValidationError("semester must be an integer between 1 and 8.")
    return value


def _validated_values(data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")

    values = {
        field: _required_text(data, field)
        for field in REQUIRED_FIELDS
        if field not in ("date_of_birth", "semester")
    }
    values["date_of_birth"] = _parse_date(data.get("date_of_birth"))
    values["semester"] = _parse_semester(data.get("semester"))

    email = values["email"]
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValidationError("email must be a valid email address.")

    address = data.get("address")
    if address is not None and (not isinstance(address, str) or not address.strip()):
        raise ValidationError("address must be a non-empty string when provided.")
    values["address"] = address.strip() if isinstance(address, str) else None
    return values


def _as_dict(profile):
    return {
        "srn": profile.srn,
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "date_of_birth": profile.date_of_birth.isoformat(),
        "gender": profile.gender,
        "address": profile.address,
        "emergency_contact_name": profile.emergency_contact_name,
        "emergency_contact_phone": profile.emergency_contact_phone,
        "program": profile.program,
        "branch": profile.branch,
        "semester": profile.semester,
    }


def _validated_changes(data):
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    unknown = set(data) - set(PERMITTED_FIELDS)
    if unknown:
        raise ValidationError("Only contact and emergency details can be updated.")
    if not data:
        raise ValidationError("At least one permitted field is required.")

    values = {}
    for field in PERMITTED_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{field} must be a non-empty string.")
        values[field] = value.strip()
    return values


def get_for_student(srn):
    return get(srn)


def request_changes(srn, user_id, data):
    profile = repository.get_by_srn(srn)
    if profile is None:
        raise NotFoundError("Student profile not found.")
    values = _validated_changes(data)
    if repository.get_pending_request(profile.id) is not None:
        raise ConflictError(
            "A profile change is already pending verification.",
            "ERR_CHANGE_PENDING",
        )
    change_request = ProfileChangeRequest(
        profile_id=profile.id, requested_by=user_id, **values
    )
    return _change_request_dict(repository.add_change_request(change_request))


def _change_request_dict(change_request):
    return {
        "id": change_request.id,
        "srn": repository.get_by_id(change_request.profile_id).srn,
        "phone": change_request.phone,
        "address": change_request.address,
        "emergency_contact_name": change_request.emergency_contact_name,
        "emergency_contact_phone": change_request.emergency_contact_phone,
        "status": change_request.status,
        "created_at": change_request.created_at.isoformat(),
    }


def approve_change(request_id):
    change_request = repository.get_change_request(request_id)
    if change_request is None:
        raise NotFoundError("Profile change request not found.")
    if change_request.status != "Pending Verification":
        raise ConflictError(
            "This profile change request has already been reviewed.",
            "ERR_CHANGE_REVIEWED",
        )
    profile = repository.get_by_id(change_request.profile_id)
    for field in PERMITTED_FIELDS:
        value = getattr(change_request, field)
        if value is not None:
            setattr(profile, field, value)
    change_request.status = "Approved"
    change_request.reviewed_at = Clock.now()
    repository.save_change_request(change_request)
    return _change_request_dict(change_request)


def reject_change(request_id):
    change_request = repository.get_change_request(request_id)
    if change_request is None:
        raise NotFoundError("Profile change request not found.")
    if change_request.status != "Pending Verification":
        raise ConflictError(
            "This profile change request has already been reviewed.",
            "ERR_CHANGE_REVIEWED",
        )
    change_request.status = "Rejected"
    change_request.reviewed_at = Clock.now()
    return _change_request_dict(repository.save_change_request(change_request))


def create(data):
    values = _validated_values(data)
    if repository.get_by_srn(values["srn"]) is not None:
        raise ConflictError("A student profile with this SRN already exists.", "ERR_DUPLICATE_SRN")
    return _as_dict(repository.add(StudentProfile(**values)))


def get(srn):
    profile = repository.get_by_srn(srn)
    if profile is None:
        raise NotFoundError("Student profile not found.")
    return _as_dict(profile)


def update(srn, data):
    profile = repository.get_by_srn(srn)
    if profile is None:
        raise NotFoundError("Student profile not found.")
    values = _validated_values(data)
    if values["srn"] != srn and repository.get_by_srn(values["srn"]) is not None:
        raise ConflictError("A student profile with this SRN already exists.", "ERR_DUPLICATE_SRN")
    for field, value in values.items():
        setattr(profile, field, value)
    return _as_dict(repository.save(profile))
