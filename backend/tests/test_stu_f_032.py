from datetime import date, timedelta

from app.attendance.models import Attendance
from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.models import NotificationOutbox
from app.common.roles import FACULTY
from app.common.settings import set_setting
from app.course.models import Course
from app.enrollment.models import ENROLLED, Enrollment
from app.extensions import db
from app.profile.models import StudentProfile


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


def setup_course(client):
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
    db.session.add(
        StudentProfile(
            srn=SRN,
            full_name="Student One",
            email="student@example.com",
            phone="9876543210",
            date_of_birth=date(2005, 1, 1),
            gender="Female",
            program="B.Tech",
            branch="Computer Science",
            semester=5,
        )
    )
    db.session.add(
        Enrollment(
            srn=SRN,
            course_code="CS301",
            semester=5,
            status=ENROLLED,
        )
    )
    db.session.commit()
    return auth(token_for(client, "faculty"))


def record_payload(attendance_date, status):
    return {
        "attendance_date": attendance_date,
        "session": "1",
        "records": [{"srn": SRN, "status": status}],
    }


def outbox_rows():
    return db.session.execute(
        db.select(NotificationOutbox)
    ).scalars().all()


def test_student_is_notified_when_attendance_crosses_threshold(client):
    headers = setup_course(client)
    set_setting("attendance_minimum_percentage", "75")

    first = client.post(
        "/api/courses/CS301/attendance",
        json=record_payload("2026-11-01", "Present"),
        headers=headers,
    )
    second = client.post(
        "/api/courses/CS301/attendance",
        json=record_payload("2026-11-02", "Absent"),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    rows = outbox_rows()
    assert len(rows) == 1
    assert rows[0].recipient == "student@example.com"
    assert rows[0].kind == "ATTENDANCE_BELOW_THRESHOLD"
    assert "CS301" in rows[0].body
    assert "50.00%" in rows[0].body
    assert Clock.now() - rows[0].created_at < timedelta(hours=1)


def test_attendance_above_threshold_does_not_notify(client):
    headers = setup_course(client)

    response = client.post(
        "/api/courses/CS301/attendance",
        json=record_payload("2026-11-01", "Present"),
        headers=headers,
    )

    assert response.status_code == 201
    assert outbox_rows() == []


def test_configured_threshold_is_used(client):
    headers = setup_course(client)
    set_setting("attendance_minimum_percentage", "50")

    first = client.post(
        "/api/courses/CS301/attendance",
        json=record_payload("2026-11-01", "Present"),
        headers=headers,
    )
    second = client.post(
        "/api/courses/CS301/attendance",
        json=record_payload("2026-11-02", "Absent"),
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert outbox_rows() == []


def test_already_below_threshold_is_not_notified_again(client):
    headers = setup_course(client)

    for index, status in enumerate(["Absent", "Absent"], start=1):
        response = client.post(
            "/api/courses/CS301/attendance",
            json=record_payload(
                (date(2026, 11, 1) + timedelta(days=index - 1)).isoformat(),
                status,
            ),
            headers=headers,
        )
        assert response.status_code == 201

    assert len(outbox_rows()) == 1
    assert db.session.execute(db.select(Attendance)).scalars().all()
