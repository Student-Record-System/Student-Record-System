from datetime import date, timedelta

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, STUDENT
from app.common.clock import Clock
from app.course.models import Course
from app.course import repository as course_repository
from app.enrollment import service as enrollment_service
from app.profile.models import StudentProfile
from app.profile import repository as profile_repository
from app.fees.models import FeeInvoice


PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS250"


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


def test_admin_generates_one_invoice_per_enrolled_student(client):
    admin = make_user("admin_050", ADMIN)
    student = make_user(SRN, STUDENT)
    profile_repository.add(StudentProfile(
        srn=SRN,
        full_name="Test Student",
        email="student050@example.com",
        phone="9876543210",
        date_of_birth=date(2005, 1, 1),
        gender="Female",
        program="B.Tech",
        branch="Computer Science",
        semester=5,
    ))
    course_repository.add(Course(
        code="CS050",
        title="Fee Course",
        credits=4,
        semester=5,
        department="Computer Science",
    ))
    enrollment_service.set_window({
        "start": (Clock.now() - timedelta(hours=2)).isoformat(),
        "end": (Clock.now() + timedelta(hours=1)).isoformat(),
    })
    student_token = token_for(client, SRN)
    client.post("/api/enrollments", json={"course_code": "CS050"},
                headers=auth(student_token))
    Clock.advance(hours=2)
    admin_token = token_for(client, admin.login_id)

    structure = client.post(
        "/api/fees/structures",
        json={"program": "B.Tech", "semester": 5, "course_code": "CS050",
              "amount": "25000"},
        headers=auth(admin_token),
    )
    generated = client.post(
        "/api/fees/invoices/generate",
        headers=auth(admin_token),
    )
    repeated = client.post(
        "/api/fees/invoices/generate",
        headers=auth(admin_token),
    )

    assert structure.status_code == 201
    assert generated.status_code == 201
    assert generated.get_json()["invoices"][0]["amount"] == "25000.00"
    assert repeated.status_code == 201
    assert repeated.get_json()["invoices"] == []
    assert FeeInvoice.query.count() == 1
    assert FeeInvoice.query.one().student_id == student.id
