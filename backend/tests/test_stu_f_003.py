from datetime import timedelta

from app.auth import repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.models import AuditEvent
from app.extensions import db

PASSWORD = "Passw0rd!"
LOGIN_ID = "PES2UG24CS001"


def create_test_user():
    user = User(
        login_id=LOGIN_ID,
        email="student@example.com",
        password_hash=hash_password(PASSWORD),
        role="STUDENT",
        is_active=True,
    )
    repository.add_user(user)
    return user


def attempt_login(client, login_id=LOGIN_ID, password=PASSWORD):
    return client.post(
        "/api/auth/login",
        json={"login_id": login_id, "password": password},
    )


def test_four_failed_attempts_do_not_lock_account(client, app):
    # TC-STU-F-003-01
    with app.app_context():
        user = create_test_user()

        for _ in range(4):
            response = attempt_login(client, password="WrongPassword!")
            assert response.status_code == 401

        db.session.refresh(user)
        assert user.failed_attempts == 4
        assert user.locked_until is None


def test_fifth_failed_attempt_locks_account(client, app):
    # TC-STU-F-003-02
    with app.app_context():
        user = create_test_user()

        for _ in range(4):
            attempt_login(client, password="WrongPassword!")

        response = attempt_login(client, password="WrongPassword!")

        assert response.status_code == 423

        db.session.refresh(user)
        assert user.failed_attempts == 5
        assert user.locked_until is not None
        assert user.locked_until >= Clock.now() + timedelta(minutes=14, seconds=59)


def test_correct_password_rejected_during_lockout(client, app):
    # TC-STU-F-003-03
    with app.app_context():
        create_test_user()

        for _ in range(5):
            attempt_login(client, password="WrongPassword!")

        response = attempt_login(client, password=PASSWORD)

        assert response.status_code == 423


def test_lockout_records_audit_event(client, app):
    # TC-STU-F-003-04
    with app.app_context():
        user = create_test_user()

        for _ in range(5):
            attempt_login(client, password="WrongPassword!")

        event = db.session.execute(
            db.select(AuditEvent).filter_by(
                event_type="ACCOUNT_LOCKED",
                user_id=user.id,
            )
        ).scalar_one_or_none()

        assert event is not None
        assert event.login_id == LOGIN_ID
        assert event.details["failed_attempts"] == 5
        assert event.details["lockout_minutes"] == 15


def test_login_succeeds_after_lockout_expires(client, app):
    # TC-STU-F-003-05
    with app.app_context():
        user = create_test_user()

        for _ in range(5):
            attempt_login(client, password="WrongPassword!")

        Clock.advance(minutes=16)

        response = attempt_login(client, password=PASSWORD)

        assert response.status_code == 200

        db.session.refresh(user)
        assert user.failed_attempts == 0
        assert user.locked_until is None


def test_successful_login_resets_failed_attempts(client, app):
    # TC-STU-F-003-06
    with app.app_context():
        user = create_test_user()

        for _ in range(3):
            attempt_login(client, password="WrongPassword!")

        response = attempt_login(client, password=PASSWORD)

        assert response.status_code == 200

        db.session.refresh(user)
        assert user.failed_attempts == 0
        assert user.locked_until is None
