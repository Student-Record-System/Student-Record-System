from datetime import date, timedelta

import pytest

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.roles import ADMIN, STUDENT
from app.course import repository as course_repository
from app.course.models import Course
from app.enrollment import repository as enrollment_repository
from app.enrollment import service as enrollment_service
from app.enrollment.models import COMPLETED, ENROLLED, Enrollment
from app.extensions import db
from app.profile import repository as profile_repository
from app.profile.models import StudentProfile

PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"


def make_user(login_id, role):
    return auth_repository.add_user(User(
        login_id=login_id,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    ))


def token_for(client, login_id):
    response = client.post(
        "/api/auth/login", json={"login_id": login_id, "password": PASSWORD}
    )
    return response.get_json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_course(code, semester=5, credits=4):
    return course_repository.add(Course(
        code=code, title=f"Course {code}", credits=credits,
        semester=semester, department="Computer Science",
    ))


def make_profile(srn=SRN, semester=5):
    return profile_repository.add(StudentProfile(
        srn=srn, full_name="Test Student", email="student@example.com",
        phone="9876543210", date_of_birth=date(2005, 1, 1), gender="Female",
        program="B.Tech", branch="Computer Science", semester=semester,
    ))


def set_window(start_hours, end_hours):
    now = Clock.now()
    enrollment_service.set_window({
        "start": (now + timedelta(hours=start_hours)).isoformat(),
        "end": (now + timedelta(hours=end_hours)).isoformat(),
    })


def enroll(client, headers, code):
    return client.post("/api/enrollments", json={"course_code": code}, headers=headers)


def error_code(response):
    return response.get_json()["error"]["code"]


@pytest.fixture()
def student_headers(client):
    make_user(SRN, STUDENT)
    make_profile()
    return auth(token_for(client, SRN))


@pytest.fixture()
def admin_headers(client):
    make_user("admin", ADMIN)
    return auth(token_for(client, "admin"))


# ---- enrolling ----

def test_student_can_enroll_when_window_open_and_rules_met(client, student_headers):  # TC-Enr-02
    make_course("CS301")
    set_window(-1, 1)

    response = enroll(client, student_headers, "CS301")

    body = response.get_json()
    assert response.status_code == 201
    assert body["course_code"] == "CS301"
    assert body["status"] == ENROLLED
    assert enrollment_repository.get_enrollment(SRN, "CS301") is not None


def test_course_code_is_not_case_sensitive(client, student_headers):
    make_course("CS301")
    set_window(-1, 1)

    response = enroll(client, student_headers, "cs301")

    assert response.status_code == 201
    assert response.get_json()["course_code"] == "CS301"


def test_enrollment_rejected_when_window_is_closed(client, student_headers):  # TC-Enr-02
    make_course("CS301")
    set_window(-3, -1)

    response = enroll(client, student_headers, "CS301")

    assert response.status_code == 409
    assert error_code(response) == "ERR_WINDOW_CLOSED"
    assert enrollment_repository.get_enrollment(SRN, "CS301") is None


def test_enrollment_rejected_when_window_is_not_configured(client, student_headers):
    make_course("CS301")

    response = enroll(client, student_headers, "CS301")

    assert response.status_code == 409
    assert error_code(response) == "ERR_WINDOW_CLOSED"


def test_enrollment_closes_when_time_moves_past_the_window(client, student_headers):
    make_course("CS301")
    make_course("CS302")
    set_window(-1, 1)
    assert enroll(client, student_headers, "CS301").status_code == 201

    Clock.advance(hours=2)
    response = enroll(client, student_headers, "CS302")

    assert response.status_code == 409
    assert error_code(response) == "ERR_WINDOW_CLOSED"


def test_course_for_another_semester_is_rejected(client, student_headers):
    make_course("CS401", semester=7)
    set_window(-1, 1)

    response = enroll(client, student_headers, "CS401")

    assert response.status_code == 409
    assert error_code(response) == "ERR_WRONG_SEMESTER"


def test_duplicate_enrollment_is_rejected(client, student_headers):
    make_course("CS301")
    set_window(-1, 1)
    assert enroll(client, student_headers, "CS301").status_code == 201

    response = enroll(client, student_headers, "CS301")

    assert response.status_code == 409
    assert error_code(response) == "ERR_ALREADY_ENROLLED"


def test_unknown_course_returns_not_found(client, student_headers):
    set_window(-1, 1)

    response = enroll(client, student_headers, "NOPE999")

    assert response.status_code == 404
    assert error_code(response) == "ERR_NOT_FOUND"


def test_student_without_a_profile_cannot_enroll(client):
    make_user(SRN, STUDENT)
    make_course("CS301")
    set_window(-1, 1)
    headers = auth(token_for(client, SRN))

    response = enroll(client, headers, "CS301")

    assert response.status_code == 404
    assert error_code(response) == "ERR_NOT_FOUND"


def test_non_student_cannot_enroll(client, admin_headers):
    make_course("CS301")
    set_window(-1, 1)

    response = enroll(client, admin_headers, "CS301")

    assert response.status_code == 403
    assert error_code(response) == "ERR_FORBIDDEN"


def test_enrollment_requires_login(client):
    response = client.post("/api/enrollments", json={"course_code": "CS301"})

    assert response.status_code == 401
    assert error_code(response) == "ERR_AUTH_FAILED"


@pytest.mark.parametrize("body", [{}, {"course_code": ""}, {"course_code": 5}])
def test_course_code_is_required(client, student_headers, body):
    response = client.post("/api/enrollments", json=body, headers=student_headers)

    assert response.status_code == 400
    assert error_code(response) == "ERR_VALIDATION"


# ---- prerequisites ----

def setup_prerequisite(client, admin_headers):
    make_course("CS201", semester=3)
    make_course("CS301")
    set_window(-1, 1)
    response = client.put(
        "/api/courses/CS301/prerequisites",
        json={"prerequisites": ["CS201"]},
        headers=admin_headers,
    )
    assert response.status_code == 200


def test_prerequisite_not_met_is_rejected(client, student_headers, admin_headers):  # TC-Enr-02
    setup_prerequisite(client, admin_headers)

    response = enroll(client, student_headers, "CS301")

    assert response.status_code == 409
    assert error_code(response) == "ERR_PREREQ_NOT_MET"
    assert "CS201" in response.get_json()["error"]["message"]


def test_prerequisite_is_met_when_the_course_is_completed(client, student_headers, admin_headers):  # TC-Enr-02
    setup_prerequisite(client, admin_headers)
    db.session.add(Enrollment(srn=SRN, course_code="CS201", semester=3, status=COMPLETED))
    db.session.commit()

    response = enroll(client, student_headers, "CS301")

    assert response.status_code == 201


def test_prerequisite_only_enrolled_does_not_count(client, student_headers, admin_headers):
    setup_prerequisite(client, admin_headers)
    db.session.add(Enrollment(srn=SRN, course_code="CS201", semester=3, status=ENROLLED))
    db.session.commit()

    response = enroll(client, student_headers, "CS301")

    assert response.status_code == 409
    assert error_code(response) == "ERR_PREREQ_NOT_MET"


def test_admin_sets_prerequisites(client, admin_headers):
    make_course("CS201", semester=3)
    make_course("CS202", semester=3)
    make_course("CS301")

    response = client.put(
        "/api/courses/cs301/prerequisites",
        json={"prerequisites": ["CS202", "cs201", "CS201"]},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "course_code": "CS301", "prerequisites": ["CS201", "CS202"],
    }


def test_setting_prerequisites_replaces_the_old_ones(client, admin_headers):
    make_course("CS201", semester=3)
    make_course("CS301")
    url = "/api/courses/CS301/prerequisites"
    client.put(url, json={"prerequisites": ["CS201"]}, headers=admin_headers)

    client.put(url, json={"prerequisites": []}, headers=admin_headers)

    assert enrollment_repository.get_prerequisite_codes("CS301") == []


def test_prerequisites_for_unknown_course_not_found(client, admin_headers):
    response = client.put(
        "/api/courses/NOPE999/prerequisites",
        json={"prerequisites": []},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_unknown_prerequisite_course_not_found(client, admin_headers):
    make_course("CS301")

    response = client.put(
        "/api/courses/CS301/prerequisites",
        json={"prerequisites": ["ZZ999"]},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_course_cannot_be_its_own_prerequisite(client, admin_headers):
    make_course("CS301")

    response = client.put(
        "/api/courses/CS301/prerequisites",
        json={"prerequisites": ["CS301"]},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert error_code(response) == "ERR_VALIDATION"


def test_non_admin_cannot_set_prerequisites(client, student_headers):
    make_course("CS301")

    response = client.put(
        "/api/courses/CS301/prerequisites",
        json={"prerequisites": []},
        headers=student_headers,
    )

    assert response.status_code == 403


# ---- enrollment window settings ----

def test_admin_can_set_and_read_the_enrollment_window(client, admin_headers):
    body = {"start": "2026-10-26T09:00:00", "end": "2026-10-30T17:00:00"}

    saved = client.put("/api/config/enrollment-window", json=body, headers=admin_headers)
    read = client.get("/api/config/enrollment-window", headers=admin_headers)

    assert saved.status_code == 200
    assert read.get_json() == body


@pytest.mark.parametrize("body", [
    {"start": "2026-10-30T09:00:00", "end": "2026-10-26T09:00:00"},
    {"start": "not-a-date", "end": "2026-10-26T09:00:00"},
    {"start": "2026-10-26T09:00:00"},
])
def test_invalid_enrollment_window_is_rejected(client, admin_headers, body):
    response = client.put("/api/config/enrollment-window", json=body, headers=admin_headers)

    assert response.status_code == 400
    assert error_code(response) == "ERR_VALIDATION"


def test_non_admin_cannot_set_the_enrollment_window(client, student_headers):
    body = {"start": "2026-10-26T09:00:00", "end": "2026-10-30T17:00:00"}

    response = client.put("/api/config/enrollment-window", json=body, headers=student_headers)

    assert response.status_code == 403