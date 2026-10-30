from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, FACULTY, STUDENT
from app.course import repository as course_repository
from app.course.models import Course
from app.enrollment.models import COMPLETED, ENROLLED, Enrollment
from app.extensions import db
from app.grades.models import PENDING_APPROVAL, StudentMark


PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"


def make_user(login_id, role):
    return auth_repository.add_user(
        User(
            login_id=login_id,
            password_hash=hash_password(PASSWORD),
            role=role,
            is_active=True,
        )
    )


def token_for(client, login_id):
    response = client.post(
        "/api/auth/login",
        json={"login_id": login_id, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.get_json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def setup_pending_mark():
    make_user(SRN, STUDENT)
    faculty = make_user("faculty", FACULTY)
    course = course_repository.add(
        Course(
            code="CS301",
            title="Database Management Systems",
            credits=4,
            semester=5,
            department="Computer Science",
            faculty_id=faculty.id,
        )
    )
    db.session.add(
        Enrollment(
            srn=SRN,
            course_code=course.code,
            semester=5,
            status=ENROLLED,
        )
    )
    db.session.add(
        StudentMark(
            course_code=course.code,
            srn=SRN,
            internal_marks=42,
            end_semester_marks=85,
            status=PENDING_APPROVAL,
            submitted_by=faculty.id,
        )
    )
    db.session.commit()


def test_student_cannot_see_pending_results(client):
    setup_pending_mark()
    headers = auth(token_for(client, SRN))

    response = client.get("/api/student/results", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == []


def test_admin_can_review_pending_marks(client):
    setup_pending_mark()
    make_user("admin", ADMIN)
    headers = auth(token_for(client, "admin"))

    response = client.get("/api/admin/marks/pending", headers=headers)

    assert response.status_code == 200
    results = response.get_json()
    assert len(results) == 1
    assert results[0]["status"] == PENDING_APPROVAL
    assert results[0]["srn"] == SRN


def test_admin_can_approve_marks_and_complete_enrollment(client):
    setup_pending_mark()
    make_user("admin", ADMIN)
    headers = auth(token_for(client, "admin"))

    response = client.post(
        f"/api/admin/marks/CS301/{SRN}/approve",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "Approved"

    mark = db.session.execute(
        db.select(StudentMark).filter_by(
            course_code="CS301",
            srn=SRN,
        )
    ).scalar_one()
    enrollment = db.session.execute(
        db.select(Enrollment).filter_by(
            course_code="CS301",
            srn=SRN,
        )
    ).scalar_one()

    assert mark.status == "Approved"
    assert enrollment.status == COMPLETED


def test_student_can_see_results_after_approval(client):
    setup_pending_mark()
    make_user("admin", ADMIN)
    admin_headers = auth(token_for(client, "admin"))

    approval = client.post(
        f"/api/admin/marks/CS301/{SRN}/approve",
        headers=admin_headers,
    )
    assert approval.status_code == 200

    student_headers = auth(token_for(client, SRN))
    response = client.get("/api/student/results", headers=student_headers)

    assert response.status_code == 200
    results = response.get_json()
    assert len(results) == 1
    assert results[0]["course_code"] == "CS301"
    assert results[0]["internal_marks"] == 42
    assert results[0]["end_semester_marks"] == 85


def test_faculty_cannot_approve_marks(client):
    setup_pending_mark()
    headers = auth(token_for(client, "faculty"))

    response = client.post(
        f"/api/admin/marks/CS301/{SRN}/approve",
        headers=headers,
    )

    assert response.status_code == 403


def test_student_cannot_approve_marks(client):
    setup_pending_mark()
    headers = auth(token_for(client, SRN))

    response = client.post(
        f"/api/admin/marks/CS301/{SRN}/approve",
        headers=headers,
    )

    assert response.status_code == 403


def test_approving_marks_twice_is_rejected(client):
    setup_pending_mark()
    make_user("admin", ADMIN)
    headers = auth(token_for(client, "admin"))
    endpoint = f"/api/admin/marks/CS301/{SRN}/approve"

    first = client.post(endpoint, headers=headers)
    second = client.post(endpoint, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "ERR_MARKS_NOT_PENDING"
