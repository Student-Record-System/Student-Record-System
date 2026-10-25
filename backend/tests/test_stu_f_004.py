import re

import pytest

from app.auth import repository
from app.auth.models import User
from app.auth.otp_model import PasswordResetOTP
from app.auth.service import hash_password, verify_password
from app.common.clock import Clock
from app.common.models import NotificationOutbox
from app.common.roles import STUDENT
from app.extensions import db


LOGIN_ID = "PES2UG24CS001"
EMAIL = "student@example.com"
PASSWORD = "OldPassw0rd!"
NEW_PASSWORD = "NewPassw0rd!"


@pytest.fixture(autouse=True)
def reset_clock():
    Clock.reset()
    yield
    Clock.reset()


def create_user(email=EMAIL):
    user = User(
        login_id=LOGIN_ID,
        email=email,
        password_hash=hash_password(PASSWORD),
        role=STUDENT,
    )
    return repository.add_user(user)


def request_otp(client, email=EMAIL):
    return client.post(
        "/api/auth/forgot-password",
        json={"email": email},
    )


def reset_password(client, otp, email=EMAIL, password=NEW_PASSWORD):
    return client.post(
        "/api/auth/reset-password",
        json={
            "email": email,
            "otp": otp,
            "new_password": password,
        },
    )


def get_otp_from_outbox():
    notification = db.session.execute(
        db.select(NotificationOutbox).filter_by(
            kind="PASSWORD_RESET_OTP"
        )
    ).scalar_one()
    match = re.search(r"OTP is: (\d{6})", notification.body)
    assert match is not None
    return match.group(1)


def test_registered_email_receives_reset_otp(client):
    create_user()

    response = request_otp(client)

    assert response.status_code == 200
    assert len(response.get_json()["message"]) > 0

    notification = db.session.execute(
        db.select(NotificationOutbox).filter_by(
            kind="PASSWORD_RESET_OTP"
        )
    ).scalar_one()

    assert notification.recipient == EMAIL
    assert notification.body.find("10 minutes") >= 0


def test_valid_otp_resets_password(client):
    user = create_user()
    request_otp(client)
    otp = get_otp_from_outbox()

    response = reset_password(client, otp)

    assert response.status_code == 200
    db.session.refresh(user)
    assert verify_password(NEW_PASSWORD, user.password_hash)
    assert not verify_password(PASSWORD, user.password_hash)

    reset_record = db.session.execute(
        db.select(PasswordResetOTP).filter_by(user_id=user.id)
    ).scalar_one()
    assert reset_record.used_at is not None


def test_invalid_otp_is_rejected(client):
    create_user()
    request_otp(client)

    response = reset_password(client, "000000")

    assert response.status_code == 400


def test_otp_expires_after_ten_minutes(client):
    create_user()
    request_otp(client)
    otp = get_otp_from_outbox()

    Clock.advance(minutes=10)

    response = reset_password(client, otp)

    assert response.status_code == 400


def test_otp_cannot_be_reused(client):
    create_user()
    request_otp(client)
    otp = get_otp_from_outbox()

    first = reset_password(client, otp)
    second = reset_password(client, otp, password="AnotherPass1!")

    assert first.status_code == 200
    assert second.status_code == 400


def test_unknown_email_does_not_reveal_account_existence(client):
    create_user()

    known = request_otp(client, EMAIL)
    unknown = request_otp(client, "unknown@example.com")

    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()

    notifications = db.session.execute(
        db.select(NotificationOutbox).filter_by(
            kind="PASSWORD_RESET_OTP"
        )
    ).scalars().all()
    assert len(notifications) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": ""},
        {"email": EMAIL, "otp": "123", "new_password": NEW_PASSWORD},
        {"email": EMAIL, "otp": "123456", "new_password": "short"},
    ],
)
def test_invalid_reset_input_is_rejected(client, payload):
    response = client.post("/api/auth/reset-password", json=payload)
    assert response.status_code == 400
