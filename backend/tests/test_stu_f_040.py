from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, FACULTY, STUDENT
from app.course import repository as course_repository
from app.course.models import Course
from app.enrollment.models import ENROLLED, Enrollment
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


def setup_course_with_enrollment(faculty_login_id="faculty"):
    faculty = make_user(faculty_login_id, FACULTY)

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
    db.session.commit()

    return faculty, course


def test_assigned_faculty_can_submit_marks(client):
    setup_course_with_enrollment()
    headers = auth(token_for(client, "faculty"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["course_code"] == "CS301"
    assert body["srn"] == SRN
    assert body["internal_marks"] == 42
    assert body["end_semester_marks"] == 85
    assert body["status"] == PENDING_APPROVAL

    saved = db.session.execute(
        db.select(StudentMark).filter_by(
            course_code="CS301",
            srn=SRN,
        )
    ).scalar_one()

    assert saved.status == PENDING_APPROVAL


def test_faculty_cannot_submit_marks_for_another_facultys_course(client):
    setup_course_with_enrollment()
    make_user("other_faculty", FACULTY)
    headers = auth(token_for(client, "other_faculty"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 403

    saved = db.session.execute(
        db.select(StudentMark).filter_by(
            course_code="CS301",
            srn=SRN,
        )
    ).scalar_one_or_none()

    assert saved is None


def test_student_cannot_submit_marks(client):
    setup_course_with_enrollment()
    make_user("student", STUDENT)
    headers = auth(token_for(client, "student"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_admin_cannot_submit_marks_through_faculty_endpoint(client):
    setup_course_with_enrollment()
    make_user("admin", ADMIN)
    headers = auth(token_for(client, "admin"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_marks_submission_requires_login(client):
    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
    )

    assert response.status_code == 401


def test_marks_for_unknown_course_return_404(client):
    make_user("faculty", FACULTY)
    headers = auth(token_for(client, "faculty"))

    response = client.post(
        "/api/courses/NOPE999/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_marks_cannot_be_submitted_for_unenrolled_student(client):
    faculty = make_user("faculty", FACULTY)

    course_repository.add(
        Course(
            code="CS301",
            title="Database Management Systems",
            credits=4,
            semester=5,
            department="Computer Science",
            faculty_id=faculty.id,
        )
    )

    headers = auth(token_for(client, "faculty"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 409
    assert (
        response.get_json()["error"]["code"]
        == "ERR_STUDENT_NOT_ENROLLED"
    )


def test_duplicate_marks_submission_is_rejected(client):
    setup_course_with_enrollment()
    headers = auth(token_for(client, "faculty"))

    body = {
        "srn": SRN,
        "internal_marks": 42,
        "end_semester_marks": 85,
    }

    first = client.post(
        "/api/courses/CS301/marks",
        json=body,
        headers=headers,
    )
    second = client.post(
        "/api/courses/CS301/marks",
        json=body,
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert (
        second.get_json()["error"]["code"]
        == "ERR_MARKS_ALREADY_SUBMITTED"
    )


def test_invalid_marks_are_rejected(client):
    setup_course_with_enrollment()
    headers = auth(token_for(client, "faculty"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "srn": SRN,
            "internal_marks": -1,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_missing_student_srn_is_rejected(client):
    setup_course_with_enrollment()
    headers = auth(token_for(client, "faculty"))

    response = client.post(
        "/api/courses/CS301/marks",
        json={
            "internal_marks": 42,
            "end_semester_marks": 85,
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"
