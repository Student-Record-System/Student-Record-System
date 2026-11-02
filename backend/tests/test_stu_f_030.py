from datetime import date

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.attendance.models import Attendance
from app.common.roles import FACULTY, STUDENT
from app.course.models import Course
from app.enrollment.models import ENROLLED, Enrollment
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


def setup_course_with_students(client):
    faculty = make_user("faculty", FACULTY)

    db.session.add(
        Course(
            code="CS301",
            title="Database Management Systems",
            credits=4,
            semester=5,
            department="Computer Science",
            faculty_id=faculty.id,
        )
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
                status=ENROLLED,
            ),
        ]
    )

    db.session.commit()

    return auth(token_for(client, "faculty"))


def attendance_payload():
    return {
        "attendance_date": "2026-11-01",
        "session": "1",
        "records": [
            {"srn": SRN1, "status": "Present"},
            {"srn": SRN2, "status": "Absent"},
        ],
    }


def test_faculty_can_record_session_attendance(client):
    headers = setup_course_with_students(client)

    response = client.post(
        "/api/courses/CS301/attendance",
        json=attendance_payload(),
        headers=headers,
    )

    assert response.status_code == 201
    assert response.get_json() == {
        "course_code": "CS301",
        "attendance_date": "2026-11-01",
        "session": "1",
        "records": [
            {"srn": SRN1, "status": "Present"},
            {"srn": SRN2, "status": "Absent"},
        ],
    }

    saved = db.session.execute(
        db.select(Attendance).order_by(Attendance.srn)
    ).scalars().all()

    assert len(saved) == 2
    assert saved[0].recorded_by is not None
    assert saved[0].status == "Present"
    assert saved[1].status == "Absent"


def test_duplicate_attendance_is_rejected(client):
    headers = setup_course_with_students(client)
    payload = attendance_payload()

    first = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    second = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert (
        second.get_json()["error"]["code"]
        == "ERR_DUPLICATE_ATTENDANCE"
    )

    saved = db.session.execute(
        db.select(Attendance)
    ).scalars().all()

    assert len(saved) == 2


def test_same_student_can_have_attendance_in_another_session(client):
    headers = setup_course_with_students(client)
    payload = attendance_payload()

    first = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    payload["session"] = "2"

    second = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201


def test_faculty_cannot_record_attendance_for_another_facultys_course(client):
    setup_course_with_students(client)
    other_faculty = make_user("other_faculty", FACULTY)
    headers = auth(token_for(client, "other_faculty"))

    response = client.post(
        "/api/courses/CS301/attendance",
        json=attendance_payload(),
        headers=headers,
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_student_cannot_record_attendance(client):
    setup_course_with_students(client)
    make_user("student", STUDENT)
    headers = auth(token_for(client, "student"))

    response = client.post(
        "/api/courses/CS301/attendance",
        json=attendance_payload(),
        headers=headers,
    )

    assert response.status_code == 403


def test_attendance_for_unenrolled_student_is_rejected(client):
    headers = setup_course_with_students(client)
    payload = attendance_payload()
    payload["records"][0]["srn"] = "UNKNOWN"

    response = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 409
    assert (
        response.get_json()["error"]["code"]
        == "ERR_STUDENT_NOT_ENROLLED"
    )

    saved = db.session.execute(
        db.select(Attendance)
    ).scalars().all()

    assert saved == []


def test_duplicate_student_in_same_request_is_rejected(client):
    headers = setup_course_with_students(client)
    payload = attendance_payload()
    payload["records"][1]["srn"] = SRN1

    response = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 409
    assert (
        response.get_json()["error"]["code"]
        == "ERR_DUPLICATE_ATTENDANCE"
    )

    saved = db.session.execute(
        db.select(Attendance)
    ).scalars().all()

    assert saved == []


def test_invalid_attendance_status_is_rejected(client):
    headers = setup_course_with_students(client)
    payload = attendance_payload()
    payload["records"][0]["status"] = "Late"

    response = client.post(
        "/api/courses/CS301/attendance",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_attendance_for_unknown_course_returns_404(client):
    make_user("faculty", FACULTY)
    headers = auth(token_for(client, "faculty"))

    response = client.post(
        "/api/courses/UNKNOWN/attendance",
        json=attendance_payload(),
        headers=headers,
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"
