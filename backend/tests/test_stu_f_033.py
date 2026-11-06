
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
                srn=SRN1,
                course_code="CS302",
                semester=5,
                status=COMPLETED,
            ),
            Enrollment(
                srn=SRN2,
                course_code="CS301",
                semester=5,
                status=ENROLLED,
            ),
        ]
    )

    db.session.commit()

    return (
        faculty,
        auth(token_for(client, "faculty")),
        auth(token_for(client, SRN1)),
        auth(token_for(client, SRN2)),
    )


def add_attendance(srn, course_code, faculty_id, records):
    attendance_records = [
        Attendance(
            srn=srn,
            course_code=course_code,
            attendance_date=date.fromisoformat(attendance_date),
            session=session,
            status=status,
            recorded_by=faculty_id,
        )
        for attendance_date, session, status in records
    ]

    db.session.add_all(attendance_records)
    db.session.commit()


def test_student_can_view_individual_attendance_records(client):
    faculty, _, student_headers, _ = setup_attendance_data(client)

    add_attendance(
        SRN1,
        "CS301",
        faculty.id,
        [
            ("2026-11-01", "1", "Present"),
            ("2026-11-02", "1", "Absent"),
        ],
    )

    response = client.get(
        "/api/students/me/attendance/records",
        headers=student_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "srn": SRN1,
        "courses": [
            {
                "course_code": "CS301",
                "records": [
                    {
                        "attendance_date": "2026-11-01",
                        "session": "1",
                        "status": "Present",
                    },
                    {
                        "attendance_date": "2026-11-02",
                        "session": "1",
                        "status": "Absent",
                    },
                ],
            },
            {
                "course_code": "CS302",
                "records": [],
            },
        ],
    }


def test_student_can_view_records_for_multiple_courses(client):
    faculty, _, student_headers, _ = setup_attendance_data(client)

    add_attendance(
        SRN1,
        "CS301",
        faculty.id,
        [("2026-11-01", "1", "Present")],
    )

    add_attendance(
        SRN1,
        "CS302",
        faculty.id,
        [("2026-11-02", "1", "Absent")],
    )

    response = client.get(
        "/api/students/me/attendance/records",
        headers=student_headers,
    )

    assert response.status_code == 200

    courses = response.get_json()["courses"]

    assert len(courses) == 2
    assert courses[0]["course_code"] == "CS301"
    assert courses[0]["records"][0]["status"] == "Present"
    assert courses[1]["course_code"] == "CS302"
    assert courses[1]["records"][0]["status"] == "Absent"


def test_course_without_attendance_records_is_included(client):
    _, _, student_headers, _ = setup_attendance_data(client)

    response = client.get(
        "/api/students/me/attendance/records",
        headers=student_headers,
    )

    assert response.status_code == 200

    courses = response.get_json()["courses"]

    assert len(courses) == 2
    assert courses[0]["records"] == []
    assert courses[1]["records"] == []


def test_attendance_records_match_faculty_submissions(client):
    faculty, faculty_headers, student_headers, _ = setup_attendance_data(client)

    submission = client.post(
        "/api/courses/CS301/attendance",
        json={
            "attendance_date": "2026-11-01",
            "session": "1",
            "records": [
                {"srn": SRN1, "status": "Present"},
                {"srn": SRN2, "status": "Absent"},
            ],
        },
        headers=faculty_headers,
    )

    assert submission.status_code == 201

    response = client.get(
        "/api/students/me/attendance/records",
        headers=student_headers,
    )

    assert response.status_code == 200

    records = response.get_json()["courses"][0]["records"]

    assert records == [
        {
            "attendance_date": "2026-11-01",
            "session": "1",
            "status": "Present",
        }
    ]


def test_attendance_records_are_ordered_by_date_and_session(client):
    faculty, _, student_headers, _ = setup_attendance_data(client)

    add_attendance(
        SRN1,
        "CS301",
        faculty.id,
        [
            ("2026-11-03", "2", "Absent"),
            ("2026-11-01", "2", "Present"),
            ("2026-11-01", "1", "Absent"),
        ],
    )

    response = client.get(
        "/api/students/me/attendance/records",
        headers=student_headers,
    )

    assert response.status_code == 200

    records = response.get_json()["courses"][0]["records"]

    assert [
        (record["attendance_date"], record["session"])
        for record in records
    ] == [
        ("2026-11-01", "1"),
        ("2026-11-01", "2"),
        ("2026-11-03", "2"),
    ]


def test_student_can_only_view_own_attendance_records(client):
    faculty, _, student1_headers, student2_headers = setup_attendance_data(client)

    add_attendance(
        SRN1,
        "CS301",
        faculty.id,
        [("2026-11-01", "1", "Present")],
    )

    add_attendance(
        SRN2,
        "CS301",
        faculty.id,
        [("2026-11-01", "1", "Absent")],
    )

    response1 = client.get(
        "/api/students/me/attendance/records",
        headers=student1_headers,
    )

    response2 = client.get(
        "/api/students/me/attendance/records",
        headers=student2_headers,
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    assert response1.get_json()["srn"] == SRN1
    assert response2.get_json()["srn"] == SRN2

    assert response1.get_json()["courses"][0]["records"][0]["status"] == "Present"
    assert response2.get_json()["courses"][0]["records"][0]["status"] == "Absent"


def test_faculty_cannot_access_student_attendance_records(client):
    _, faculty_headers, _, _ = setup_attendance_data(client)

    response = client.get(
        "/api/students/me/attendance/records",
        headers=faculty_headers,
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_access_attendance_records(client):
    response = client.get(
        "/api/students/me/attendance/records",
    )

    assert response.status_code == 401
