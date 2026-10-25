from io import BytesIO

import pytest

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, STUDENT

PASSWORD = "Passw0rd!"

PROFILE = {
    "srn": "PES2UG24CS012",
    "full_name": "Asha Rao",
    "email": "asha.rao@example.com",
    "phone": "9876543210",
    "date_of_birth": "2005-04-12",
    "gender": "Female",
    "program": "B.Tech",
    "branch": "Computer Science",
    "semester": 5,
}

# Minimal valid PDF header for file-signature validation.
VALID_PDF = b"%PDF-1.4\nTest document content\n%%EOF"


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
    assert response.status_code == 200
    return response.get_json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def create_profile(client, headers, profile=PROFILE):
    response = client.post(
        "/api/students", json=profile, headers=headers
    )
    assert response.status_code == 201
    return response


def upload_pdf(client, srn, headers, content=VALID_PDF, filename="id.pdf"):
    return client.post(
        f"/api/students/{srn}/documents",
        data={"file": (BytesIO(content), filename)},
        headers=headers,
        content_type="multipart/form-data",
    )


@pytest.fixture()
def setup_users_and_profile(client, monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))

    make_user("admin", ADMIN)
    make_user(PROFILE["srn"], STUDENT)

    admin_headers = auth_header(token_for(client, "admin"))
    student_headers = auth_header(token_for(client, PROFILE["srn"]))

    create_profile(client, admin_headers)

    return admin_headers, student_headers


def test_admin_can_upload_and_student_can_download_document(
    client, setup_users_and_profile
):
    admin_headers, student_headers = setup_users_and_profile

    uploaded = upload_pdf(client, PROFILE["srn"], admin_headers)

    assert uploaded.status_code == 201
    metadata = uploaded.get_json()
    assert metadata["srn"] == PROFILE["srn"]
    assert metadata["filename"] == "id.pdf"
    assert metadata["content_type"] == "application/pdf"
    assert metadata["size_bytes"] == len(VALID_PDF)

    downloaded = client.get(
        f"/api/students/{PROFILE['srn']}/documents/{metadata['id']}",
        headers=student_headers,
    )

    assert downloaded.status_code == 200
    assert downloaded.data == VALID_PDF
    assert downloaded.mimetype == "application/pdf"


def test_student_cannot_upload_document(
    client, setup_users_and_profile
):
    _, student_headers = setup_users_and_profile

    response = upload_pdf(client, PROFILE["srn"], student_headers)

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("notes.txt", VALID_PDF),
        ("fake.jpg", b"MZ executable content"),
        ("empty.pdf", b""),
    ],
)
def test_invalid_document_is_rejected(
    client, setup_users_and_profile, filename, content
):
    admin_headers, _ = setup_users_and_profile

    response = upload_pdf(
        client, PROFILE["srn"], admin_headers, content, filename
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_oversized_document_is_rejected(
    client, setup_users_and_profile, monkeypatch
):
    admin_headers, _ = setup_users_and_profile
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_BYTES", "16")

    response = upload_pdf(
        client, PROFILE["srn"], admin_headers,
        b"%PDF-1.4\n" + b"x" * 100,
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_student_cannot_download_another_students_document(
    client, setup_users_and_profile
):
    admin_headers, student_headers = setup_users_and_profile

    other_profile = PROFILE | {
        "srn": "PES2UG24CS099",
        "email": "other@example.com",
    }
    create_profile(client, admin_headers, other_profile)
    uploaded = upload_pdf(client, other_profile["srn"], admin_headers)
    document_id = uploaded.get_json()["id"]

    response = client.get(
        f"/api/students/{other_profile['srn']}/documents/{document_id}",
        headers=student_headers,
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_missing_document_returns_not_found(
    client, setup_users_and_profile
):
    admin_headers, _ = setup_users_and_profile

    response = client.get(
        f"/api/students/{PROFILE['srn']}/documents/99999",
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_missing_profile_returns_not_found(
    client, setup_users_and_profile
):
    admin_headers, _ = setup_users_and_profile

    response = upload_pdf(client, "UNKNOWN-SRN", admin_headers)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_upload_requires_authentication(client):
    response = upload_pdf(client, PROFILE["srn"], {})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ERR_AUTH_FAILED"
