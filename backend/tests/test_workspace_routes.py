from app.auth.models import User
from app.auth.service import hash_password
from app.common.audit import record_event
from app.common.roles import ADMIN, STUDENT
from app.extensions import db


PASSWORD = "safe-password-123"
SRN = "PES2UG24CS999"


def _user(login_id, role):
    user = User(
        login_id=login_id,
        email=f"{login_id.lower()}@example.com",
        password_hash=hash_password(PASSWORD),
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _headers(client, login_id):
    response = client.post(
        "/api/auth/login",
        json={"login_id": login_id, "password": PASSWORD},
    )
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def _profile():
    return {
        "srn": SRN,
        "full_name": "Student Example",
        "email": "student@example.com",
        "phone": "9876543210",
        "date_of_birth": "2004-01-01",
        "gender": "Female",
        "program": "B.Tech",
        "branch": "CSE",
        "semester": 5,
    }


def test_admin_can_list_pending_profile_change_requests(client):
    _user("admin", ADMIN)
    _user(SRN, STUDENT)
    admin_headers = _headers(client, "admin")

    assert client.post("/api/students", json=_profile(), headers=admin_headers).status_code == 201
    change = client.patch(
        "/api/students/me",
        json={"phone": "9123456789"},
        headers=_headers(client, SRN),
    )

    response = client.get("/api/students/requests", headers=admin_headers)
    assert response.status_code == 200
    assert response.get_json()["requests"][0]["id"] == change.get_json()["id"]


def test_student_can_list_own_documents_and_admin_can_search_audit(client, app):
    _user("admin", ADMIN)
    _user(SRN, STUDENT)
    admin_headers = _headers(client, "admin")
    assert client.post("/api/students", json=_profile(), headers=admin_headers).status_code == 201

    documents = client.get(
        f"/api/students/{SRN}/documents",
        headers=_headers(client, SRN),
    )
    assert documents.status_code == 200
    assert documents.get_json() == {"srn": SRN, "documents": []}

    with app.app_context():
        record_event("WORKSPACE_TEST", login_id="admin")
        db.session.commit()
    audit = client.get("/api/admin/audit-events?event_type=WORKSPACE_TEST", headers=admin_headers)
    assert audit.status_code == 200
    assert audit.get_json()["events"][0]["event_type"] == "WORKSPACE_TEST"
