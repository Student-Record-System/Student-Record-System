import pytest

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.models import AuditEvent
from app.common.roles import ADMIN, FACULTY, STUDENT
from app.course.models import Course
from app.enrollment.models import COMPLETED, Enrollment
from app.extensions import db
from app.grades.models import PENDING_APPROVAL, StudentMark
from app.reviews import repository as review_repository

PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"
OTHER_SRN = "PES2UG24CS999"
REASON = "I think question 4 of the end-semester paper was marked incorrectly."


def make_user(login_id, role):
    return auth_repository.add_user(User(
        login_id=login_id,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    ))


def headers_for(client, login_id):
    response = client.post(
        "/api/auth/login", json={"login_id": login_id, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def add_result(course_code="CS301", srn=SRN, status="Approved"):
    if db.session.execute(db.select(Course).filter_by(code=course_code)).first() is None:
        db.session.add(Course(
            code=course_code, title=f"Course {course_code}", credits=4,
            semester=1, department="Computer Science",
        ))
    db.session.add(Enrollment(
        srn=srn, course_code=course_code, semester=1, status=COMPLETED,
    ))
    db.session.add(StudentMark(
        course_code=course_code, srn=srn, internal_marks=80,
        end_semester_marks=90, status=status, submitted_by=1,
    ))
    db.session.commit()


def request_review(client, headers, course_code="CS301", reason=REASON):
    return client.post(
        "/api/grade-reviews",
        json={"course_code": course_code, "reason": reason},
        headers=headers,
    )


def error_code(response):
    return response.get_json()["error"]["code"]


@pytest.fixture()
def student(client):
    make_user(SRN, STUDENT)
    return headers_for(client, SRN)


@pytest.fixture()
def admin(client):
    make_user("admin", ADMIN)
    return headers_for(client, "admin")


# ---- raising a request ----

def test_student_can_request_review_inside_the_window(client, student):  # TC-Grd-05
    add_result()

    response = request_review(client, student)

    body = response.get_json()
    assert response.status_code == 201
    assert body["srn"] == SRN
    assert body["course_code"] == "CS301"
    assert body["reason"] == REASON
    assert body["status"] == "Pending Review"
    assert review_repository.get_review(SRN, "CS301") is not None


def test_course_code_is_not_case_sensitive(client, student):
    add_result()

    response = request_review(client, student, course_code="cs301")

    assert response.status_code == 201
    assert response.get_json()["course_code"] == "CS301"


def test_request_just_before_the_default_window_ends_is_accepted(client, student):  # TC-Grd-05
    add_result()
    Clock.advance(days=6, hours=23)

    assert request_review(client, student).status_code == 201


def test_request_after_the_default_window_is_rejected(client, student):  # TC-Grd-05
    add_result()
    Clock.advance(days=7, hours=1)

    response = request_review(client, student)

    assert response.status_code == 409
    assert error_code(response) == "ERR_REVIEW_WINDOW_CLOSED"
    assert review_repository.get_review(SRN, "CS301") is None


def test_window_length_is_taken_from_the_admin_setting(client, student, admin):  # TC-Grd-05
    add_result("CS301")
    add_result("CS302")
    client.put("/api/config/review-window", json={"days": 1}, headers=admin)
    Clock.advance(days=2)
    assert error_code(request_review(client, student, "CS301")) == "ERR_REVIEW_WINDOW_CLOSED"

    client.put("/api/config/review-window", json={"days": 30}, headers=admin)

    assert request_review(client, student, "CS302").status_code == 201


def test_window_counts_from_approval_not_from_submission(client, student):  # TC-Grd-05
    add_result(status=PENDING_APPROVAL)
    Clock.advance(days=10)  # submitted long ago, approved only now
    mark = db.session.execute(
        db.select(StudentMark).filter_by(srn=SRN, course_code="CS301")
    ).scalar_one()
    mark.status = "Approved"
    db.session.commit()

    assert request_review(client, student).status_code == 201


def test_result_that_is_not_published_cannot_be_reviewed(client, student):
    add_result(status=PENDING_APPROVAL)

    response = request_review(client, student)

    assert response.status_code == 404
    assert error_code(response) == "ERR_NO_RESULT"


def test_unknown_course_returns_not_found(client, student):
    response = request_review(client, student, course_code="NOPE999")

    assert response.status_code == 404
    assert error_code(response) == "ERR_NO_RESULT"


def test_student_cannot_review_someone_elses_result(client, student):
    add_result(srn=OTHER_SRN)

    response = request_review(client, student)

    assert response.status_code == 404
    assert error_code(response) == "ERR_NO_RESULT"


def test_second_request_for_the_same_course_is_rejected(client, student):
    add_result()
    assert request_review(client, student).status_code == 201

    response = request_review(client, student)

    assert response.status_code == 409
    assert error_code(response) == "ERR_REVIEW_EXISTS"
    assert len(review_repository.list_reviews(SRN)) == 1


def test_request_is_written_to_the_audit_log(client, student):
    add_result()
    request_review(client, student)

    event = db.session.execute(
        db.select(AuditEvent).filter_by(event_type="GRADE_REVIEW_REQUESTED")
    ).scalar_one()
    assert event.login_id == SRN
    assert event.details == {"course_code": "CS301"}


@pytest.mark.parametrize("body", [
    {},
    {"course_code": "CS301"},
    {"reason": REASON},
    {"course_code": "", "reason": REASON},
    {"course_code": "CS301", "reason": "   "},
    {"course_code": 301, "reason": REASON},
    {"course_code": "CS301", "reason": "x" * 1001},
])
def test_invalid_request_body_is_rejected(client, student, body):
    add_result()

    response = client.post("/api/grade-reviews", json=body, headers=student)

    assert response.status_code == 400
    assert error_code(response) == "ERR_VALIDATION"


def test_non_student_cannot_request_a_review(client, admin):
    add_result()

    response = request_review(client, admin)

    assert response.status_code == 403
    assert error_code(response) == "ERR_FORBIDDEN"


def test_faculty_cannot_request_a_review(client):
    make_user("faculty", FACULTY)
    add_result()

    response = request_review(client, headers_for(client, "faculty"))

    assert response.status_code == 403


def test_request_requires_login(client):
    response = client.post("/api/grade-reviews", json={"course_code": "CS301", "reason": REASON})

    assert response.status_code == 401
    assert error_code(response) == "ERR_AUTH_FAILED"


# ---- listing requests ----

def test_student_sees_only_their_own_requests(client, student):
    make_user(OTHER_SRN, STUDENT)
    add_result("CS301")
    add_result("CS302", srn=OTHER_SRN)
    request_review(client, student, "CS301")
    request_review(client, headers_for(client, OTHER_SRN), "CS302")

    response = client.get("/api/grade-reviews", headers=student)

    assert response.status_code == 200
    assert [r["course_code"] for r in response.get_json()] == ["CS301"]


def test_admin_sees_all_requests(client, student, admin):
    make_user(OTHER_SRN, STUDENT)
    add_result("CS301")
    add_result("CS302", srn=OTHER_SRN)
    request_review(client, student, "CS301")
    request_review(client, headers_for(client, OTHER_SRN), "CS302")

    response = client.get("/api/grade-reviews", headers=admin)

    assert response.status_code == 200
    assert {r["srn"] for r in response.get_json()} == {SRN, OTHER_SRN}


def test_listing_requires_login(client):
    assert client.get("/api/grade-reviews").status_code == 401


def test_faculty_cannot_list_requests(client):
    make_user("faculty", FACULTY)

    response = client.get("/api/grade-reviews", headers=headers_for(client, "faculty"))

    assert response.status_code == 403


# ---- review window setting ----

def test_review_window_defaults_to_seven_days(client, admin):
    response = client.get("/api/config/review-window", headers=admin)

    assert response.status_code == 200
    assert response.get_json() == {"days": 7}


def test_admin_can_set_and_read_the_review_window(client, admin):
    saved = client.put("/api/config/review-window", json={"days": 14}, headers=admin)
    read = client.get("/api/config/review-window", headers=admin)

    assert saved.status_code == 200
    assert read.get_json() == {"days": 14}


@pytest.mark.parametrize("body", [
    {}, {"days": 0}, {"days": 91}, {"days": -3}, {"days": "7"}, {"days": 2.5}, {"days": True},
])
def test_invalid_review_window_is_rejected(client, admin, body):
    response = client.put("/api/config/review-window", json=body, headers=admin)

    assert response.status_code == 400
    assert error_code(response) == "ERR_VALIDATION"


def test_student_cannot_change_the_review_window(client, student):
    response = client.put("/api/config/review-window", json={"days": 30}, headers=student)

    assert response.status_code == 403