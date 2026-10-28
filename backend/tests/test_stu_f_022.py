
from datetime import date

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, STUDENT
from app.course import repository as course_repository
from app.course.models import Course
from app.enrollment import repository as enrollment_repository
from app.enrollment.models import ENROLLED, Enrollment
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
        "/api/auth/login",
        json={"login_id": login_id, "password": PASSWORD},
    )
    return response.get_json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_course(code, semester=5, credits=4):
    return course_repository.add(Course(
        code=code,
        title=f"Course {code}",
        credits=credits,
        semester=semester,
        department="Computer Science",
    ))


def make_profile(srn=SRN, semester=5):
    return profile_repository.add(StudentProfile(
        srn=srn,
        full_name="Test Student",
        email=f"{srn.lower()}@example.com",
        phone="9876543210",
        date_of_birth=date(2005, 1, 1),
        gender="Female",
        program="B.Tech",
        branch="Computer Science",
        semester=semester,
    ))


def make_enrollment(srn, course, status=ENROLLED):
    enrollment = Enrollment(
        srn=srn,
        course_code=course.code,
        semester=course.semester,
        status=status,
    )
    return enrollment_repository.add_enrollment(enrollment)


def test_student_can_view_current_semester_courses(client):
    make_user(SRN, STUDENT)
    make_profile(semester=5)
    course1 = make_course("CS301", semester=5, credits=4)
    course2 = make_course("CS302", semester=5, credits=3)
    make_enrollment(SRN, course1)
    make_enrollment(SRN, course2)

    token = token_for(client, SRN)
    response = client.get(
        "/api/enrollments/current",
        headers=auth(token),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["semester"] == 5
    assert len(body["courses"]) == 2
    assert body["total_credits"] == 7
    assert {course["course_code"] for course in body["courses"]} == {
        "CS301", "CS302"
    }


def test_current_courses_include_course_details(client):
    make_user(SRN, STUDENT)
    make_profile(semester=5)
    course = make_course("CS303", semester=5, credits=4)
    make_enrollment(SRN, course)

    token = token_for(client, SRN)
    response = client.get(
        "/api/enrollments/current",
        headers=auth(token),
    )

    assert response.status_code == 200
    item = response.get_json()["courses"][0]
    assert item["course_code"] == "CS303"
    assert item["title"] == "Course CS303"
    assert item["credits"] == 4


def test_current_courses_exclude_other_semesters(client):
    make_user(SRN, STUDENT)
    make_profile(semester=5)
    current_course = make_course("CS304", semester=5, credits=4)
    other_course = make_course("CS204", semester=4, credits=3)
    make_enrollment(SRN, current_course)
    make_enrollment(SRN, other_course)

    token = token_for(client, SRN)
    response = client.get(
        "/api/enrollments/current",
        headers=auth(token),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert [item["course_code"] for item in body["courses"]] == ["CS304"]
    assert body["total_credits"] == 4


def test_current_courses_exclude_completed_enrollments(client):
    make_user(SRN, STUDENT)
    make_profile(semester=5)
    course = make_course("CS305", semester=5, credits=4)
    make_enrollment(SRN, course, status="Completed")

    token = token_for(client, SRN)
    response = client.get(
        "/api/enrollments/current",
        headers=auth(token),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["courses"] == []
    assert body["total_credits"] == 0


def test_current_courses_require_login(client):
    response = client.get("/api/enrollments/current")

    assert response.status_code == 401


def test_non_student_cannot_view_current_courses(client):
    make_user("admin", ADMIN)
    token = token_for(client, "admin")

    response = client.get(
        "/api/enrollments/current",
        headers=auth(token),
    )

    assert response.status_code == 403
