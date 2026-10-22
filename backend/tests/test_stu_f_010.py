from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, STUDENT
from app.extensions import db

PASSWORD = "Passw0rd!"
PROFILE = {
    "srn": "PES2UG24CS010",
    "full_name": "Asha Rao",
    "email": "asha.rao@example.com",
    "phone": "9876543210",
    "date_of_birth": "2005-04-12",
    "gender": "Female",
    "program": "B.Tech",
    "branch": "Computer Science",
    "semester": 5,
}


def make_user(login_id, role):
    return auth_repository.add_user(User(
        login_id=login_id,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    ))


def token_for(client, login_id):
    response = client.post(
        "/api/auth/login", json={"login_id": login_id, "password": PASSWORD}
    )
    return response.get_json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_and_retrieve_profile(client):
    make_user("admin", ADMIN)
    token = token_for(client, "admin")

    created = client.post(
        "/api/students", json=PROFILE, headers=auth_header(token)
    )
    retrieved = client.get(
        f"/api/students/{PROFILE['srn']}", headers=auth_header(token)
    )

    assert created.status_code == 201
    assert retrieved.status_code == 200
    assert retrieved.get_json() == PROFILE | {
        "address": None,
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
    }


def test_non_admin_cannot_create_profile(client):
    make_user("student", STUDENT)
    token = token_for(client, "student")

    response = client.post(
        "/api/students", json=PROFILE, headers=auth_header(token)
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_profile_requires_mandatory_fields(client):
    make_user("admin", ADMIN)
    token = token_for(client, "admin")
    incomplete = {key: value for key, value in PROFILE.items() if key != "branch"}

    response = client.post(
        "/api/students", json=incomplete, headers=auth_header(token)
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_profile_srn_must_be_unique(client):
    make_user("admin", ADMIN)
    token = token_for(client, "admin")
    headers = auth_header(token)

    assert client.post("/api/students", json=PROFILE, headers=headers).status_code == 201
    duplicate = client.post("/api/students", json=PROFILE, headers=headers)

    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "ERR_DUPLICATE_SRN"


def test_admin_can_update_profile(client):
    make_user("admin", ADMIN)
    token = token_for(client, "admin")
    headers = auth_header(token)
    client.post("/api/students", json=PROFILE, headers=headers)
    updated = PROFILE | {"semester": 6, "address": "Bengaluru"}

    response = client.put(
        f"/api/students/{PROFILE['srn']}", json=updated, headers=headers
    )

    assert response.status_code == 200
    assert response.get_json() == updated | {
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
    }


def test_missing_profile_returns_not_found(client):
    make_user("admin", ADMIN)
    token = token_for(client, "admin")

    response = client.get(
        "/api/students/UNKNOWN", headers=auth_header(token)
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_student_can_view_own_profile(client):
    make_user(PROFILE["srn"], STUDENT)
    make_user("admin", ADMIN)
    admin_headers = auth_header(token_for(client, "admin"))
    client.post("/api/students", json=PROFILE, headers=admin_headers)

    response = client.get(
        "/api/students/me",
        headers=auth_header(token_for(client, PROFILE["srn"])),
    )

    assert response.status_code == 200
    assert response.get_json()["srn"] == PROFILE["srn"]


def test_student_change_is_pending_until_admin_approves(client):
    make_user(PROFILE["srn"], STUDENT)
    make_user("admin", ADMIN)
    admin_headers = auth_header(token_for(client, "admin"))
    client.post("/api/students", json=PROFILE, headers=admin_headers)
    student_headers = auth_header(token_for(client, PROFILE["srn"]))

    submitted = client.patch(
        "/api/students/me",
        json={
            "phone": "9123456780",
            "address": "Bengaluru",
            "emergency_contact_name": "Ravi Rao",
            "emergency_contact_phone": "9988776655",
        },
        headers=student_headers,
    )

    assert submitted.status_code == 202
    request_body = submitted.get_json()
    assert request_body["status"] == "Pending Verification"

    before_approval = client.get("/api/students/me", headers=student_headers)
    assert before_approval.get_json()["phone"] == PROFILE["phone"]

    approved = client.post(
        f"/api/students/requests/{request_body['id']}/approve",
        headers=admin_headers,
    )
    after_approval = client.get("/api/students/me", headers=student_headers)

    assert approved.status_code == 200
    assert approved.get_json()["status"] == "Approved"
    assert after_approval.get_json()["phone"] == "9123456780"
    assert after_approval.get_json()["emergency_contact_name"] == "Ravi Rao"


def test_student_cannot_update_academic_fields(client):
    make_user(PROFILE["srn"], STUDENT)
    make_user("admin", ADMIN)
    admin_headers = auth_header(token_for(client, "admin"))
    client.post("/api/students", json=PROFILE, headers=admin_headers)

    response = client.patch(
        "/api/students/me",
        json={"semester": 6},
        headers=auth_header(token_for(client, PROFILE["srn"])),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_student_cannot_submit_second_pending_change(client):
    make_user(PROFILE["srn"], STUDENT)
    make_user("admin", ADMIN)
    admin_headers = auth_header(token_for(client, "admin"))
    client.post("/api/students", json=PROFILE, headers=admin_headers)
    student_headers = auth_header(token_for(client, PROFILE["srn"]))
    payload = {"phone": "9123456780"}

    assert client.patch(
        "/api/students/me", json=payload, headers=student_headers
    ).status_code == 202
    duplicate = client.patch(
        "/api/students/me", json=payload, headers=student_headers
    )

    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "ERR_CHANGE_PENDING"
