import pytest
from app.grades.service import _calculate_grade
from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import STUDENT, FACULTY
from app.course.models import Course
from app.enrollment.models import COMPLETED, Enrollment
from app.extensions import db
from app.grades.models import StudentMark


PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"


def make_student():
    return auth_repository.add_user(
        User(
            login_id=SRN,
            password_hash=hash_password(PASSWORD),
            role=STUDENT,
            is_active=True,
        )
    )

def make_faculty():
    return auth_repository.add_user(
        User(
            login_id="faculty",
            password_hash=hash_password(PASSWORD),
            role=FACULTY,
            is_active=True,
        )
    )

def token_for(client):
    response = client.post(
        "/api/auth/login",
        json={"login_id": SRN, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.get_json()["access_token"]

def token_for_user(client, login_id):
    response = client.post(
        "/api/auth/login",
        json={"login_id": login_id, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.get_json()["access_token"]

def auth(token):
    return {"Authorization": f"Bearer {token}"}


def add_approved_result(
    course_code,
    semester,
    credits,
    internal_marks,
    end_semester_marks,
):
    course = Course(
        code=course_code,
        title=f"Course {course_code}",
        credits=credits,
        semester=semester,
        department="Computer Science",
    )
    db.session.add(course)

    db.session.add(
        Enrollment(
            srn=SRN,
            course_code=course_code,
            semester=semester,
            status=COMPLETED,
        )
    )

    db.session.add(
        StudentMark(
            course_code=course_code,
            srn=SRN,
            internal_marks=internal_marks,
            end_semester_marks=end_semester_marks,
            status="Approved",
            submitted_by=1,
        )
    )
    db.session.commit()


def test_student_results_include_total_grade_and_credits(client):
    make_student()
    add_approved_result("CS301", 1, 4, 80, 90)

    response = client.get(
        "/api/student/results",
        headers=auth(token_for(client)),
    )

    assert response.status_code == 200
    result = response.get_json()[0]

    assert result["total_marks"] == 85
    assert result["grade"] == "A"
    assert result["grade_points"] == 9
    assert result["credits"] == 4


def test_semester_gpa_and_cgpa_are_credit_weighted(client):
    make_student()

    add_approved_result("CS301", 1, 3, 90, 100)
    add_approved_result("CS302", 1, 1, 80, 90)
    add_approved_result("CS401", 2, 2, 70, 80)

    response = client.get(
        "/api/student/gpa",
        headers=auth(token_for(client)),
    )

    assert response.status_code == 200
    result = response.get_json()

    assert result["semester_gpa"] == [
        {"semester": 1, "gpa": 9.75},
        {"semester": 2, "gpa": 8.0},
    ]
    assert result["cgpa"] == 9.17


def test_pending_marks_are_excluded_from_gpa_and_cgpa(client):
    make_student()

    add_approved_result("CS301", 1, 4, 90, 90)

    course = Course(
        code="CS302",
        title="Pending Course",
        credits=3,
        semester=1,
        department="Computer Science",
    )
    db.session.add(course)
    db.session.add(
        StudentMark(
            course_code="CS302",
            srn=SRN,
            internal_marks=0,
            end_semester_marks=0,
            status="Pending Approval",
            submitted_by=1,
        )
    )
    db.session.commit()

    response = client.get(
        "/api/student/gpa",
        headers=auth(token_for(client)),
    )

    assert response.status_code == 200
    result = response.get_json()

    assert result["semester_gpa"] == [
        {"semester": 1, "gpa": 10.0},
    ]
    assert result["cgpa"] == 10.0


@pytest.mark.parametrize(
    "marks, expected_grade, expected_points",
    [
        (100, "S", 10),
        (90, "S", 10),
        (89, "A", 9),
        (80, "A", 9),
        (79, "B", 8),
        (70, "B", 8),
        (69, "C", 7),
        (60, "C", 7),
        (59, "D", 6),
        (50, "D", 6),
        (49, "E", 5),
        (40, "E", 5),
        (39, "F", 0),
        (0, "F", 0),
    ],
)
def test_grade_boundaries(marks, expected_grade, expected_points):
    total, grade, points = _calculate_grade(marks, marks)

    assert total == marks
    assert grade == expected_grade
    assert points == expected_points


def test_student_with_no_approved_results_has_zero_gpa_and_cgpa(client):
    make_student()

    response = client.get(
        "/api/student/gpa",
        headers=auth(token_for(client)),
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "semester_gpa": [],
        "cgpa": 0.0,
    }


def test_gpa_and_cgpa_match_manual_calculation_for_10_records(client):
    make_student()

    records = [
        ("CS501", 1, 3, 90, 90),
        ("CS502", 1, 4, 80, 80),
        ("CS503", 1, 2, 70, 70),
        ("CS504", 2, 3, 60, 60),
        ("CS505", 2, 3, 50, 50),
        ("CS506", 2, 1, 40, 40),
        ("CS507", 3, 4, 39, 39),
        ("CS508", 3, 2, 100, 100),
        ("CS509", 3, 3, 89, 89),
        ("CS510", 3, 1, 79, 79),
    ]

    for record in records:
        add_approved_result(*record)

    response = client.get(
        "/api/student/gpa",
        headers=auth(token_for(client)),
    )

    assert response.status_code == 200

    result = response.get_json()

    # Manually calculated semester GPAs
    assert result["semester_gpa"] == [
        {"semester": 1, "gpa": 9.11},
        {"semester": 2, "gpa": 6.29},
        {"semester": 3, "gpa": 5.5},
    ]

    # Manually calculated overall CGPA
    assert result["cgpa"] == 6.96

def test_unauthenticated_user_cannot_access_gpa(client):
    response = client.get("/api/student/gpa")

    assert response.status_code == 401


def test_faculty_cannot_access_student_gpa(client):
    make_faculty()

    response = client.get(
        "/api/student/gpa",
        headers=auth(token_for_user(client, "faculty")),
    )

    assert response.status_code == 403
