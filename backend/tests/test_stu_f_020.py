from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, STUDENT

PASSWORD = "Passw0rd!"
COURSE = {
    "code": "CS301",
    "title": "Database Management Systems",
    "credits": 4,
    "semester": 5,
    "department": "Computer Science",
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


def test_admin_can_define_course_and_course_appears_in_catalogue(client):
    make_user("admin", ADMIN)
    headers = auth_header(token_for(client, "admin"))

    created = client.post("/api/courses", json=COURSE, headers=headers)
    catalogue = client.get("/api/courses", headers=headers)

    assert created.status_code == 201
    assert created.get_json() == COURSE
    assert catalogue.status_code == 200
    assert catalogue.get_json() == [COURSE]


def test_student_can_view_course_catalogue(client):
    make_user("admin", ADMIN)
    make_user("student", STUDENT)
    admin_headers = auth_header(token_for(client, "admin"))
    student_headers = auth_header(token_for(client, "student"))
    client.post("/api/courses", json=COURSE, headers=admin_headers)

    response = client.get("/api/courses", headers=student_headers)

    assert response.status_code == 200
    assert response.get_json() == [COURSE]


def test_non_admin_cannot_define_course(client):
    make_user("student", STUDENT)
    headers = auth_header(token_for(client, "student"))

    response = client.post("/api/courses", json=COURSE, headers=headers)

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_course_code_must_be_unique(client):
    make_user("admin", ADMIN)
    headers = auth_header(token_for(client, "admin"))
    client.post("/api/courses", json=COURSE, headers=headers)

    duplicate = client.post(
        "/api/courses", json=COURSE | {"code": "cs301"}, headers=headers
    )

    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "ERR_DUPLICATE_COURSE"


def test_course_fields_are_validated(client):
    make_user("admin", ADMIN)
    headers = auth_header(token_for(client, "admin"))

    response = client.post(
        "/api/courses",
        json=COURSE | {"credits": 0, "semester": 9},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_course_catalogue_requires_login(client):
    response = client.get("/api/courses")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ERR_AUTH_FAILED"
