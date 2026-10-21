import pytest
from flask import jsonify

from app.auth import repository
from app.auth.access import roles_required
from app.auth.models import User
from app.auth.service import GENERIC_LOGIN_ERROR, hash_password
from app.common.roles import ADMIN, STUDENT
from app.extensions import db

PASSWORD = "Passw0rd!"


def make_user(login_id="PES2UG24CS001", role=STUDENT, is_active=True):
    return repository.add_user(User(
        login_id=login_id,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=is_active,
    ))


def login(client, login_id, password):
    return client.post("/api/auth/login", json={"login_id": login_id, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client_with_routes(app):
    # A throwaway protected route, only for these tests.
    @app.get("/api/_test/admin-only")
    @roles_required(ADMIN)
    def admin_only():
        return jsonify({"ok": True})

    return app.test_client()


def test_login_with_correct_credentials_returns_token(client):  # TC-Auth-02
    make_user()
    response = login(client, "PES2UG24CS001", PASSWORD)
    body = response.get_json()
    assert response.status_code == 200
    assert body["access_token"]
    assert body["user"]["role"] == STUDENT


def test_wrong_password_returns_generic_error(client):  # TC-Auth-02
    make_user()
    response = login(client, "PES2UG24CS001", "wrong-password")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ERR_AUTH_FAILED"
    assert response.get_json()["error"]["message"] == GENERIC_LOGIN_ERROR


def test_unknown_id_gets_same_error_as_wrong_password(client):  # TC-Sec-07
    make_user()
    wrong_password = login(client, "PES2UG24CS001", "wrong-password")
    unknown_id = login(client, "NOBODY", "wrong-password")
    assert unknown_id.status_code == wrong_password.status_code == 401
    assert unknown_id.get_json() == wrong_password.get_json()


def test_missing_fields_returns_validation_error(client):
    response = client.post("/api/auth/login", json={"login_id": "PES2UG24CS001"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_inactive_account_cannot_log_in(client):
    make_user(is_active=False)
    response = login(client, "PES2UG24CS001", PASSWORD)
    assert response.status_code == 401


def test_password_is_stored_as_a_hash(app):  # TC-Sec-02
    user = make_user()
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$2")


def test_route_without_token_is_rejected(client_with_routes):
    response = client_with_routes.get("/api/_test/admin-only")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ERR_AUTH_FAILED"


def test_student_token_is_forbidden_on_admin_route(client_with_routes):
    make_user(role=STUDENT)
    token = login(client_with_routes, "PES2UG24CS001", PASSWORD).get_json()["access_token"]
    response = client_with_routes.get("/api/_test/admin-only", headers=auth_header(token))
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_admin_token_is_allowed_on_admin_route(client_with_routes):
    make_user(login_id="admin", role=ADMIN)
    token = login(client_with_routes, "admin", PASSWORD).get_json()["access_token"]
    response = client_with_routes.get("/api/_test/admin-only", headers=auth_header(token))
    assert response.status_code == 200


def test_token_of_deactivated_account_is_refused(client_with_routes):  # TC-Sec-12
    user = make_user(login_id="admin", role=ADMIN)
    token = login(client_with_routes, "admin", PASSWORD).get_json()["access_token"]
    user.is_active = False
    db.session.commit()
    response = client_with_routes.get("/api/_test/admin-only", headers=auth_header(token))
    assert response.status_code == 401