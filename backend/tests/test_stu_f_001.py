import re
from datetime import timedelta

import pytest

from app.auth import repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.models import NotificationOutbox
from app.common.roles import ADMIN, ALL_ROLES, STUDENT
from app.extensions import db

PASSWORD = "Passw0rd!"


def make_user(login_id, role):
    return repository.add_user(
        User(login_id=login_id, password_hash=hash_password(PASSWORD), role=role)
    )


def token_for(client, login_id):
    response = client.post("/api/auth/login", json={"login_id": login_id, "password": PASSWORD})
    return response.get_json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def new_user_payload(**overrides):
    payload = {"login_id": "PES2UG24CS500", "email": "student@example.com", "role": STUDENT}
    payload.update(overrides)
    return payload


def outbox_rows():
    return db.session.execute(db.select(NotificationOutbox)).scalars().all()


@pytest.fixture()
def admin_headers(client):
    make_user("admin", ADMIN)
    return auth(token_for(client, "admin"))


def test_admin_creates_account_and_credentials_are_sent(client, admin_headers):  # TC-Auth-01
    response = client.post("/api/users", json=new_user_payload(), headers=admin_headers)
    body = response.get_json()
    assert response.status_code == 201
    assert body["login_id"] == "PES2UG24CS500"
    assert body["role"] == STUDENT
    assert "password" not in body and "password_hash" not in body

    rows = outbox_rows()
    assert len(rows) == 1
    assert rows[0].recipient == "student@example.com"
    assert rows[0].kind == "ACCOUNT_CREATED"
    assert Clock.now() - rows[0].created_at < timedelta(minutes=2)


def test_emailed_credentials_let_the_new_user_log_in(client, admin_headers):  # TC-Auth-01
    client.post("/api/users", json=new_user_payload(), headers=admin_headers)
    password = re.search(r"Temporary password: (\S+)", outbox_rows()[0].body).group(1)

    assert repository.get_user_by_login_id("PES2UG24CS500").password_hash != password
    response = client.post(
        "/api/auth/login", json={"login_id": "PES2UG24CS500", "password": password}
    )
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == STUDENT


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_be_assigned(client, admin_headers, role):
    response = client.post("/api/users", json=new_user_payload(role=role), headers=admin_headers)
    assert response.status_code == 201
    assert repository.get_user_by_login_id("PES2UG24CS500").role == role


def test_non_admin_cannot_create_accounts(client):
    make_user("PES2UG24CS001", STUDENT)
    headers = auth(token_for(client, "PES2UG24CS001"))
    response = client.post("/api/users", json=new_user_payload(), headers=headers)
    assert response.status_code == 403
    assert repository.get_user_by_login_id("PES2UG24CS500") is None


def test_creating_account_requires_login(client):
    response = client.post("/api/users", json=new_user_payload())
    assert response.status_code == 401


def test_duplicate_login_id_is_rejected(client, admin_headers):
    client.post("/api/users", json=new_user_payload(), headers=admin_headers)
    response = client.post("/api/users", json=new_user_payload(), headers=admin_headers)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "ERR_USER_EXISTS"
    assert len(outbox_rows()) == 1


@pytest.mark.parametrize("overrides", [
    {"role": "Janitor"},
    {"email": "not-an-email"},
    {"login_id": ""},
    {"email": None},
])
def test_invalid_input_is_rejected(client, admin_headers, overrides):
    response = client.post("/api/users", json=new_user_payload(**overrides), headers=admin_headers)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"