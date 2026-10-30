from datetime import date

import pytest

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, FACULTY, STUDENT
from app.course import repository as course_repository
from app.course.models import Course
from app.enrollment.models import COMPLETED, ENROLLED, Enrollment
from app.extensions import db
from app.profile.models import StudentProfile


PASSWORD = "Passw0rd!"


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


def make_course(code="CS301"):
    return course_repository.add(
        Course(
            code=code,
            title=f"Course {code}",
            credits=4,
            semester=5,
            department="Computer Science",
        )
    )


def make_profile(srn, full_name, email):
    db.session.add(
        StudentProfile(
            srn=srn,
            full_name=full_name,
            email=email,
            phone="9876543210",
            date_of_birth=date(2005, 1, 1),
            gender="Female",
            program="B.Tech",
            branch="Computer Science",
            semester=5,
        )
    )
    db.session.commit()


def assign_faculty(client, admin_headers, code, faculty_login_id):
    return client.put(
        f"/api/courses/{code}/faculty",
        json={"faculty_login_id": faculty_login_id},
        headers=admin_headers,
    )


@pytest.fixture()
def setup_users(client):
    make_user("admin", ADMIN)
    make_user("faculty1", FACULTY)
    make_user("faculty2", FACULTY)
    make_user("student1", STUDENT)

    return {
        "admin": auth(token_for(client, "admin")),
        "faculty1": auth(token_for(client, "faculty1")),
        "faculty2": auth(token_for(client, "faculty2")),
        "student1": auth(token_for(client, "student1")),
    }


def test_admin_can_assign_faculty_to_course(client, setup_users):
    make_course("CS301")

    response = assign_faculty(
        client, setup_users["admin"], "CS301", "faculty1"
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "course_code": "CS301",
        "faculty_login_id": "faculty1",
    }


def test_non_admin_cannot_assign_faculty(client, setup_users):
    make_course("CS301")

    response = assign_faculty(
        client, setup_users["faculty1"], "CS301", "faculty1"
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_assignment_rejects_nonexistent_faculty(client, setup_users):
    make_course("CS301")

    response = assign_faculty(
        client, setup_users["admin"], "CS301", "unknown"
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_assignment_rejects_student_account(client, setup_users):
    make_course("CS301")

    response = assign_faculty(
        client, setup_users["admin"], "CS301", "student1"
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_assignment_to_unknown_course_returns_404(client, setup_users):
    response = assign_faculty(
        client, setup_users["admin"], "NOPE999", "faculty1"
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_assigned_faculty_can_view_course_roster(client, setup_users):
    make_course("CS301")
    make_profile("SRN002", "Student B", "b@example.com")
    make_profile("SRN001", "Student A", "a@example.com")

    db.session.add_all(
        [
            Enrollment(
                srn="SRN002",
                course_code="CS301",
                semester=5,
                status=ENROLLED,
            ),
            Enrollment(
                srn="SRN001",
                course_code="CS301",
                semester=5,
                status=ENROLLED,
            ),
        ]
    )
    db.session.commit()

    assignment = assign_faculty(
        client, setup_users["admin"], "CS301", "faculty1"
    )
    assert assignment.status_code == 200

    response = client.get(
        "/api/courses/CS301/roster",
        headers=setup_users["faculty1"],
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "course_code": "CS301",
        "course_title": "Course CS301",
        "students": [
            {
                "srn": "SRN001",
                "full_name": "Student A",
                "email": "a@example.com",
                "branch": "Computer Science",
                "semester": 5,
            },
            {
                "srn": "SRN002",
                "full_name": "Student B",
                "email": "b@example.com",
                "branch": "Computer Science",
                "semester": 5,
            },
        ],
    }


def test_faculty_cannot_view_another_facultys_roster(client, setup_users):
    make_course("CS301")
    assign_faculty(client, setup_users["admin"], "CS301", "faculty1")

    response = client.get(
        "/api/courses/CS301/roster",
        headers=setup_users["faculty2"],
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


@pytest.mark.parametrize("user_type", ["admin", "student1"])
def test_non_faculty_cannot_view_roster(client, setup_users, user_type):
    make_course("CS301")
    assign_faculty(client, setup_users["admin"], "CS301", "faculty1")

    response = client.get(
        "/api/courses/CS301/roster",
        headers=setup_users[user_type],
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_roster_requires_login(client):
    response = client.get("/api/courses/CS301/roster")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ERR_AUTH_FAILED"


def test_roster_for_unknown_course_returns_404(client, setup_users):
    response = client.get(
        "/api/courses/NOPE999/roster",
        headers=setup_users["faculty1"],
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_roster_excludes_completed_enrollments(client, setup_users):
    make_course("CS301")
    make_profile("SRN001", "Enrolled Student", "enrolled@example.com")
    make_profile("SRN002", "Completed Student", "completed@example.com")

    db.session.add_all(
        [
            Enrollment(
                srn="SRN001",
                course_code="CS301",
                semester=5,
                status=ENROLLED,
            ),
            Enrollment(
                srn="SRN002",
                course_code="CS301",
                semester=5,
                status=COMPLETED,
            ),
        ]
    )
    db.session.commit()

    assign_faculty(client, setup_users["admin"], "CS301", "faculty1")

    response = client.get(
        "/api/courses/CS301/roster",
        headers=setup_users["faculty1"],
    )

    assert response.status_code == 200
    students = response.get_json()["students"]
    assert [student["srn"] for student in students] == ["SRN001"]