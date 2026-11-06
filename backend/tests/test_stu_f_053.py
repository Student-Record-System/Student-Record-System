
from datetime import timedelta

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.clock import Clock
from app.common.models import NotificationOutbox
from app.common.roles import ADMIN, STUDENT
from app.extensions import db
from app.fees import service
from app.fees.models import FeeInvoice, FeeReminderLog

PASSWORD = "Passw0rd!"


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


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_invoice(student, due_date, status="UNPAID"):
    invoice = FeeInvoice(
        invoice_number=f"TEST-{student.id}-{due_date}-{status}",
        student_id=student.id,
        description="Semester tuition fee",
        amount=25000,
        currency="INR",
        status=status,
        due_date=due_date,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice


def test_admin_can_get_default_reminder_settings(client):
    admin = make_user("admin_reminder_default", ADMIN)
    token = token_for(client, admin.login_id)

    response = client.get(
        "/api/fees/reminder-settings",
        headers=auth(token),
    )

    assert response.status_code == 200
    assert response.get_json()["reminder_settings"]["days_before_due"] == 3


def test_admin_can_update_reminder_settings(client):
    admin = make_user("admin_reminder_update", ADMIN)
    token = token_for(client, admin.login_id)

    response = client.put(
        "/api/fees/reminder-settings",
        headers=auth(token),
        json={"days_before_due": 5},
    )

    assert response.status_code == 200
    assert response.get_json()["reminder_settings"]["days_before_due"] == 5

    get_response = client.get(
        "/api/fees/reminder-settings",
        headers=auth(token),
    )

    assert get_response.status_code == 200
    assert get_response.get_json()["reminder_settings"]["days_before_due"] == 5


def test_admin_cannot_configure_invalid_reminder_days(client):
    admin = make_user("admin_reminder_invalid", ADMIN)
    token = token_for(client, admin.login_id)

    for invalid_value in [-1, 31, 2.5, True, "5"]:
        response = client.put(
            "/api/fees/reminder-settings",
            headers=auth(token),
            json={"days_before_due": invalid_value},
        )
        assert response.status_code == 400


def test_reminder_settings_requires_days_before_due(client):
    admin = make_user("admin_reminder_missing", ADMIN)
    token = token_for(client, admin.login_id)

    response = client.put(
        "/api/fees/reminder-settings",
        headers=auth(token),
        json={},
    )

    assert response.status_code == 400


def test_student_cannot_access_reminder_settings(client):
    student = make_user("student_reminder_access", STUDENT)
    token = token_for(client, student.login_id)

    get_response = client.get(
        "/api/fees/reminder-settings",
        headers=auth(token),
    )

    put_response = client.put(
        "/api/fees/reminder-settings",
        headers=auth(token),
        json={"days_before_due": 5},
    )

    assert get_response.status_code == 403
    assert put_response.status_code == 403


def test_reminder_settings_requires_authentication(client):
    response = client.get("/api/fees/reminder-settings")
    assert response.status_code == 401


def test_scheduled_reminder_is_sent_to_student(app):
    with app.app_context():
        student = make_user("student_reminder_send", STUDENT)

        days_before_due = 3
        due_date = Clock.now().date() + timedelta(days=days_before_due)

        invoice = make_invoice(student, due_date)

        service.configure_fee_reminders(days_before_due)

        result = service.send_scheduled_fee_reminders()

        assert result["sent_count"] == 1
        assert result["skipped_count"] == 0
        assert result["target_date"] == due_date.isoformat()

        notification = NotificationOutbox.query.filter_by(
            recipient=student.login_id,
            kind="FEE_REMINDER",
        ).first()

        assert notification is not None
        assert notification.subject == "Fee Payment Reminder"
        assert invoice.invoice_number in notification.body
        assert due_date.isoformat() in notification.body

        reminder = FeeReminderLog.query.filter_by(
            invoice_id=invoice.id,
        ).first()

        assert reminder is not None
        assert reminder.days_before_due == days_before_due


def test_duplicate_reminder_is_not_sent_twice(app):
    with app.app_context():
        student = make_user("student_reminder_duplicate", STUDENT)

        due_date = Clock.now().date() + timedelta(days=3)
        invoice = make_invoice(student, due_date)

        service.configure_fee_reminders(3)

        first_result = service.send_scheduled_fee_reminders()
        second_result = service.send_scheduled_fee_reminders()

        assert first_result["sent_count"] == 1
        assert second_result["sent_count"] == 0
        assert second_result["skipped_count"] == 1

        notifications = NotificationOutbox.query.filter_by(
            recipient=student.login_id,
            kind="FEE_REMINDER",
        ).count()

        assert notifications == 1

        reminders = FeeReminderLog.query.filter_by(
            invoice_id=invoice.id,
        ).count()

        assert reminders == 1


def test_paid_invoice_does_not_receive_reminder(app):
    with app.app_context():
        student = make_user("student_reminder_paid", STUDENT)

        due_date = Clock.now().date() + timedelta(days=3)
        make_invoice(student, due_date, status="PAID")

        service.configure_fee_reminders(3)

        result = service.send_scheduled_fee_reminders()

        assert result["sent_count"] == 0

        notification_count = NotificationOutbox.query.filter_by(
            recipient=student.login_id,
            kind="FEE_REMINDER",
        ).count()

        assert notification_count == 0


def test_cancelled_invoice_does_not_receive_reminder(app):
    with app.app_context():
        student = make_user("student_reminder_cancelled", STUDENT)

        due_date = Clock.now().date() + timedelta(days=3)
        make_invoice(student, due_date, status="CANCELLED")

        service.configure_fee_reminders(3)

        result = service.send_scheduled_fee_reminders()

        assert result["sent_count"] == 0

        notification_count = NotificationOutbox.query.filter_by(
            recipient=student.login_id,
            kind="FEE_REMINDER",
        ).count()

        assert notification_count == 0


def test_invoice_without_due_date_does_not_receive_reminder(app):
    with app.app_context():
        student = make_user("student_reminder_no_date", STUDENT)

        make_invoice(student, None)

        service.configure_fee_reminders(3)

        result = service.send_scheduled_fee_reminders()

        assert result["sent_count"] == 0

        notification_count = NotificationOutbox.query.filter_by(
            recipient=student.login_id,
            kind="FEE_REMINDER",
        ).count()

        assert notification_count == 0


def test_reminder_is_sent_only_on_configured_date(app):
    with app.app_context():
        student = make_user("student_reminder_date", STUDENT)

        due_date = Clock.now().date() + timedelta(days=5)
        make_invoice(student, due_date)

        service.configure_fee_reminders(3)

        result = service.send_scheduled_fee_reminders()

        assert result["sent_count"] == 0

        notification_count = NotificationOutbox.query.filter_by(
            recipient=student.login_id,
            kind="FEE_REMINDER",
        ).count()

        assert notification_count == 0


def test_zero_days_before_due_is_supported(app):
    with app.app_context():
        student = make_user("student_reminder_zero", STUDENT)

        due_date = Clock.now().date()
        invoice = make_invoice(student, due_date)

        service.configure_fee_reminders(0)

        result = service.send_scheduled_fee_reminders()

        assert result["sent_count"] == 1
        assert result["target_date"] == due_date.isoformat()

        reminder = FeeReminderLog.query.filter_by(
            invoice_id=invoice.id,
        ).first()

        assert reminder is not None
        assert reminder.days_before_due == 0
