from datetime import date

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.attendance.models import Attendance
from app.common.roles import FACULTY, STUDENT
from app.course.models import Course
from app.enrollment.models import COMPLETED, ENROLLED, Enrollment
from app.extensions import db
from app.profile.models import StudentProfile


PASSWORD = "Passw0rd!"
SRN1 = "PES2UG24CS252"
SRN2 = "PES2UG24CS253"


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


def setup_attendance_data(client):
    faculty = make_user("faculty", FACULTY)
    make_user(SRN1, STUDENT)
    make_user(SRN2, STUDENT)

    db.session.add_all(
        [
            Course(
                code="CS301",
                title="Database Management Systems",
                credits=4,
                semester=5,
                department="Computer Science",
                faculty_id=faculty.id,
            ),
            Course(
                code="CS302",
                title="Operating Systems",
                credits=4,
                semester=5,
                department="Computer Science",
                faculty_id=faculty.id,
            ),
        ]
    )

    db.session.add_all(
        [
            StudentProfile(
                srn=SRN1,
                full_name="Student One",
                email="student1@example.com",
                phone="9876543210",
                date_of_birth=date(2005, 1, 1),
                gender="Female",
                program="B.Tech",
                branch="Computer Science",
                semester=5,
            ),
            StudentProfile(
                srn=SRN2,
                full_name="Student Two",
                email="student2@example.com",
                phone="9876543211",
                date_of_birth=date(2005, 2, 1),
                gender="Female",
                program="B.Tech",
                branch="Computer Science",
                semester=5,
            ),
        ]
    )

    db.session.add_all(
        [
            Enrollment(
                srn=SRN1,
                course_code="CS301",
                semester=5,
                status=ENROLLED,
            ),
            Enrollment(
                srn=SRN2,
                course_code="CS301",
                semester=5,
                status=COMPLETED,
            ),
            Enrollment(
                srn=SRN1,
                course_code="CS302",
                semester=5,
                status=COMPLETED,
            ),
        ]
    )

    db.session.commit()

    return (
        auth(token_for(client, "faculty")),
        auth(token_for(client, SRN1)),
        auth(token_for(client, SRN2)),
    )


def add_attendance(srn, course_code, statuses):
    records = [
        Attendance(
            srn=srn,
            course_code=course_code,
            attendance_date=date(2026, 11, 1 + index),
            session=str(index + 1),
            status=status,
            recorded_by=1,
        )
        for index, status in enumerate(statuses)
    ]

    db.session.add_all(records)
    db.session.commit()


def test_faculty_can_view_course_attendance_summary(client):
    faculty_headers, _, _ = setup_attendance_data(client)

    add_attendance(SRN1, "CS301", ["Present", "Present", "Absent"])
    add_attendance(SRN2, "CS301", ["Present", "Absent"])

    response = client.get(
        "/api/courses/CS301/attendance/summary",
        headers=faculty_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "course_code": "CS301",
        "students": [
            {
                "srn": SRN1,
                "present_sessions": 2,
                "absent_sessions": 1,
                "total_sessions": 3,
                "attendance_percentage": 66.67,
            },
            {
                "srn": SRN2,
                "present_sessions": 1,
                "absent_sessions": 1,
                "total_sessions": 2,
                "attendance_percentage": 50.0,
            },
        ],
    }


def test_student_can_view_own_attendance_summary(client):
    _, student_headers, _ = setup_attendance_data(client)

    add_attendance(SRN1, "CS301", ["Present", "Present", "Absent"])

    response = client.get(
        "/api/students/me/attendance",
        headers=student_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "srn": SRN1,
        "courses": [
            {
                "course_code": "CS301",
                "present_sessions": 2,
                "absent_sessions": 1,
                "total_sessions": 3,
                "attendance_percentage": 66.67,
            },
            {
                "course_code": "CS302",
                "present_sessions": 0,
                "absent_sessions": 0,
                "total_sessions": 0,
                "attendance_percentage": None,
            },
        ],
    }


def test_completed_enrollment_is_included_in_student_summary(client):
    _, _, student_headers = setup_attendance_data(client)

    response = client.get(
        "/api/students/me/attendance",
        headers=student_headers,
    )

    assert response.status_code == 200

    courses = response.get_json()["courses"]
    course_codes = [course["course_code"] for course in courses]

    assert "CS301" in course_codes


def test_faculty_cannot_view_another_facultys_course_summary(client):
    setup_attendance_data(client)

    other_faculty = make_user("other_faculty", FACULTY)
    headers = auth(token_for(client, "other_faculty"))

    response = client.get(
        "/api/courses/CS301/attendance/summary",
        headers=headers,
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_student_cannot_access_faculty_course_summary(client):
    _, student_headers, _ = setup_attendance_data(client)

    response = client.get(
        "/api/courses/CS301/attendance/summary",
        headers=student_headers,
    )

    assert response.status_code == 403


def test_faculty_cannot_access_student_attendance_summary(client):
    faculty_headers, _, _ = setup_attendance_data(client)

    response = client.get(
        "/api/students/me/attendance",
        headers=faculty_headers,
    )

    assert response.status_code == 403


def test_unknown_course_summary_returns_404(client):
    faculty_headers, _, _ = setup_attendance_data(client)

    response = client.get(
        "/api/courses/UNKNOWN/attendance/summary",
        headers=faculty_headers,
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_attendance_summary_updates_after_new_attendance_entry(client):
    faculty_headers, _, _ = setup_attendance_data(client)

    initial_response = client.get(
        "/api/courses/CS301/attendance/summary",
        headers=faculty_headers,
    )

    assert initial_response.status_code == 200

    initial_student = initial_response.get_json()["students"][0]

    assert initial_student["total_sessions"] == 0
    assert initial_student["attendance_percentage"] is None

    attendance_response = client.post(
        "/api/courses/CS301/attendance",
        json={
            "attendance_date": "2026-11-01",
            "session": "1",
            "records": [
                {"srn": SRN1, "status": "Present"},
            ],
        },
        headers=faculty_headers,
    )

    assert attendance_response.status_code == 201

    updated_response = client.get(
        "/api/courses/CS301/attendance/summary",
        headers=faculty_headers,
    )

    assert updated_response.status_code == 200

    updated_student = updated_response.get_json()["students"][0]

    assert updated_student["present_sessions"] == 1
    assert updated_student["absent_sessions"] == 0
    assert updated_student["total_sessions"] == 1
    assert updated_student["attendance_percentage"] == 100.0
