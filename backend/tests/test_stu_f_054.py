from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.roles import ADMIN, STUDENT
from app.course import repository as course_repository
from app.course.models import Course
from app.enrollment import service as enrollment_service
from app.extensions import db
from app.fees.models import FeeEnrollmentOverride, FeeInvoice
from app.profile import repository as profile_repository
from app.profile.models import StudentProfile

PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"
THRESHOLD_URL = "/api/fees/enrollment-threshold"
OVERRIDES_URL = "/api/fees/enrollment-overrides"


def make_user(login_id, role):
    return auth_repository.add_user(User(
        login_id=login_id,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    ))


def token_for(client, login_id):
    response = client.post(
        "/api/auth/login",
        json={"login_id": login_id, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.get_json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_profile(srn=SRN, semester=5):
    return profile_repository.add(StudentProfile(
        srn=srn,
        full_name="Test Student",
        email="student@example.com",
        phone="9876543210",
        date_of_birth=date(2005, 1, 1),
        gender="Female",
        program="B.Tech",
        branch="Computer Science",
        semester=semester,
    ))


def make_course(code="CS301"):
    return course_repository.add(Course(
        code=code,
        title=f"Course {code}",
        credits=4,
        semester=5,
        department="Computer Science",
    ))


def set_window():
    now = Clock.now()
    enrollment_service.set_window({
        "start": (now - timedelta(hours=1)).isoformat(),
        "end": (now + timedelta(hours=1)).isoformat(),
    })


def create_invoice(client, admin_headers, student_id, amount="25000.00"):
    return client.post(
        "/api/fees/invoices",
        headers=admin_headers,
        json={
            "student_id": student_id,
            "description": "Semester tuition fee",
            "amount": amount,
        },
    )


def error_code(response):
    return response.get_json()["error"]["code"]


@pytest.fixture()
def student_data(client):
    student = make_user(SRN, STUDENT)
    make_profile()
    return student, auth(token_for(client, SRN))


@pytest.fixture()
def admin_data(client):
    admin = make_user("admin_fee_test", ADMIN)
    return admin, auth(token_for(client, admin.login_id))


# ---- threshold configuration ----

def test_admin_can_read_default_enrollment_threshold(client, admin_data):
    _, headers = admin_data

    response = client.get(THRESHOLD_URL, headers=headers)

    assert response.status_code == 200
    assert response.get_json()["threshold"] == "0.00"


def test_admin_can_update_enrollment_threshold(client, admin_data):
    _, headers = admin_data

    response = client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["threshold"] == "10000.00"

    read = client.get(THRESHOLD_URL, headers=headers)
    assert read.status_code == 200
    assert read.get_json()["threshold"] == "10000.00"


@pytest.mark.parametrize("body", [
    {},
    {"threshold": "-100.00"},
    {"threshold": "invalid"},
    {"threshold": ""},
    {"threshold": None},
])
def test_invalid_enrollment_threshold_is_rejected(
    client, admin_data, body
):
    _, headers = admin_data

    response = client.put(
        THRESHOLD_URL,
        json=body,
        headers=headers,
    )

    assert response.status_code == 400
    assert error_code(response) == "ERR_VALIDATION"


def test_student_cannot_read_enrollment_threshold(client, student_data):
    _, headers = student_data

    response = client.get(THRESHOLD_URL, headers=headers)

    assert response.status_code == 403


def test_student_cannot_update_enrollment_threshold(client, student_data):
    _, headers = student_data

    response = client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=headers,
    )

    assert response.status_code == 403


# ---- enrollment restriction ----

def test_student_with_dues_above_threshold_cannot_enroll(
    client, student_data, admin_data
):
    student, student_headers = student_data
    _, admin_headers = admin_data

    make_course()
    set_window()

    create_invoice(client, admin_headers, student.id, "25000.00")

    client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=admin_headers,
    )

    response = client.post(
        "/api/enrollments",
        json={"course_code": "CS301"},
        headers=student_headers,
    )

    assert response.status_code == 409
    assert error_code(response) == "ERR_FEE_DUES_RESTRICTION"


def test_student_with_dues_below_threshold_can_enroll(
    client, student_data, admin_data
):
    student, student_headers = student_data
    _, admin_headers = admin_data

    make_course()
    set_window()

    create_invoice(client, admin_headers, student.id, "5000.00")

    client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=admin_headers,
    )

    response = client.post(
        "/api/enrollments",
        json={"course_code": "CS301"},
        headers=student_headers,
    )

    assert response.status_code == 201


def test_student_with_dues_equal_to_threshold_can_enroll(
    client, student_data, admin_data
):
    student, student_headers = student_data
    _, admin_headers = admin_data

    make_course()
    set_window()

    create_invoice(client, admin_headers, student.id, "10000.00")

    client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=admin_headers,
    )

    response = client.post(
        "/api/enrollments",
        json={"course_code": "CS301"},
        headers=student_headers,
    )

    assert response.status_code == 201


def test_paid_invoice_does_not_count_as_outstanding_dues(
    client, student_data, admin_data
):
    student, student_headers = student_data
    _, admin_headers = admin_data

    make_course()
    set_window()

    invoice_response = create_invoice(
        client, admin_headers, student.id, "25000.00"
    )
    assert invoice_response.status_code == 201

    invoice_id = invoice_response.get_json()["invoice"]["id"]
    invoice = db.session.get(FeeInvoice, invoice_id)
    invoice.status = "PAID"
    db.session.commit()

    client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=admin_headers,
    )

    response = client.post(
        "/api/enrollments",
        json={"course_code": "CS301"},
        headers=student_headers,
    )

    assert response.status_code == 201


# ---- administrator overrides ----

def test_admin_override_allows_student_to_enroll(
    client, student_data, admin_data
):
    student, student_headers = student_data
    admin, admin_headers = admin_data

    make_course()
    set_window()

    create_invoice(client, admin_headers, student.id, "25000.00")

    client.put(
        THRESHOLD_URL,
        json={"threshold": "10000.00"},
        headers=admin_headers,
    )

    override_response = client.post(
        OVERRIDES_URL,
        headers=admin_headers,
        json={
            "student_srn": SRN,
            "semester": 5,
            "reason": "Approved by the finance department",
        },
    )

    assert override_response.status_code == 201

    response = client.post(
        "/api/enrollments",
        json={"course_code": "CS301"},
        headers=student_headers,
    )

    assert response.status_code == 201


def test_admin_override_is_recorded_with_reason_and_admin(
    client, student_data, admin_data
):
    student, _ = student_data
    admin, admin_headers = admin_data

    response = client.post(
        OVERRIDES_URL,
        headers=admin_headers,
        json={
            "student_srn": SRN,
            "semester": 5,
            "reason": "Approved by the finance department",
        },
    )

    assert response.status_code == 201

    override = FeeEnrollmentOverride.query.filter_by(
        student_id=student.id,
        semester=5,
    ).first()

    assert override is not None
    assert override.admin_user_id == admin.id
    assert override.reason == "Approved by the finance department"
    assert override.created_at is not None


def test_duplicate_override_is_rejected(
    client, student_data, admin_data
):
    _, _ = student_data
    _, admin_headers = admin_data

    body = {
        "student_srn": SRN,
        "semester": 5,
        "reason": "Approved by the finance department",
    }

    first = client.post(
        OVERRIDES_URL,
        json=body,
        headers=admin_headers,
    )
    second = client.post(
        OVERRIDES_URL,
        json=body,
        headers=admin_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.parametrize("body", [
    {},
    {"student_srn": SRN, "semester": 0, "reason": "Approved"},
    {"student_srn": SRN, "semester": 9, "reason": "Approved"},
    {"student_srn": SRN, "semester": 5, "reason": ""},
    {"student_srn": "UNKNOWN", "semester": 5, "reason": "Approved"},
])
def test_invalid_override_data_is_rejected(
    client, admin_data, student_data, body
):
    _, headers = admin_data

    response = client.post(
        OVERRIDES_URL,
        json=body,
        headers=headers,
    )

    assert response.status_code in (400, 404)


def test_student_cannot_create_override(client, student_data):
    _, headers = student_data

    response = client.post(
        OVERRIDES_URL,
        headers=headers,
        json={
            "student_srn": SRN,
            "semester": 5,
            "reason": "Approved",
        },
    )

    assert response.status_code == 403


def test_admin_can_list_enrollment_overrides(
    client, student_data, admin_data
):
    _, _ = student_data
    _, admin_headers = admin_data

    client.post(
        OVERRIDES_URL,
        headers=admin_headers,
        json={
            "student_srn": SRN,
            "semester": 5,
            "reason": "Approved",
        },
    )

    response = client.get(OVERRIDES_URL, headers=admin_headers)

    assert response.status_code == 200
    assert len(response.get_json()["overrides"]) == 1


def test_admin_can_filter_overrides_by_student_srn(
    client, student_data, admin_data
):
    _, _ = student_data
    _, admin_headers = admin_data

    client.post(
        OVERRIDES_URL,
        headers=admin_headers,
        json={
            "student_srn": SRN,
            "semester": 5,
            "reason": "Approved",
        },
    )

    response = client.get(
        f"{OVERRIDES_URL}?student_srn={SRN}",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert len(response.get_json()["overrides"]) == 1


def test_student_cannot_list_enrollment_overrides(
    client, student_data
):
    _, headers = student_data

    response = client.get(OVERRIDES_URL, headers=headers)

    assert response.status_code == 403