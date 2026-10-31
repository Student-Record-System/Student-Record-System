from io import BytesIO

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, STUDENT
from app.extensions import db
from app.fees import gateways
from app.fees.models import FeeInvoice, Payment

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


def create_invoice(client, admin_token, student_id):
    return client.post(
        "/api/fees/invoices",
        headers=auth(admin_token),
        json={
            "student_id": student_id,
            "description": "Semester tuition fee",
            "amount": "25000.00",
        },
    )


def test_admin_can_create_invoice(client):
    admin = make_user("admin_fee", ADMIN)
    student = make_user("student_fee", STUDENT)

    admin_token = token_for(client, admin.login_id)

    response = create_invoice(client, admin_token, student.id)

    assert response.status_code == 201
    invoice = response.get_json()["invoice"]
    assert invoice["amount"] == "25000.00"
    assert invoice["status"] == "UNPAID"


def test_student_can_view_own_invoices(client):
    admin = make_user("admin_list", ADMIN)
    student = make_user("student_list", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_token = token_for(client, student.login_id)

    create_invoice(client, admin_token, student.id)

    response = client.get(
        "/api/fees/invoices",
        headers=auth(student_token),
    )

    assert response.status_code == 200
    assert len(response.get_json()["invoices"]) == 1


def test_student_can_initiate_payment(client):
    admin = make_user("admin_pay", ADMIN)
    student = make_user("student_pay", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_token = token_for(client, student.login_id)

    invoice_response = create_invoice(client, admin_token, student.id)
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_token),
    )

    assert response.status_code == 201
    payment = response.get_json()["payment"]
    assert payment["status"] == "PENDING"
    assert payment["amount"] == "25000.00"


def test_student_cannot_pay_another_students_invoice(client):
    admin = make_user("admin_other", ADMIN)
    student_one = make_user("student_one", STUDENT)
    student_two = make_user("student_two", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_two_token = token_for(client, student_two.login_id)

    invoice_response = create_invoice(
        client,
        admin_token,
        student_one.id,
    )
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_two_token),
    )

    assert response.status_code == 403


def test_student_cannot_change_invoice_amount(client):
    admin = make_user("admin_amount", ADMIN)
    student = make_user("student_amount", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_token = token_for(client, student.login_id)

    invoice_response = create_invoice(client, admin_token, student.id)
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_token),
        json={"amount": "1.00"},
    )

    assert response.status_code == 201
    assert response.get_json()["payment"]["amount"] == "25000.00"


def test_payment_confirmation_and_receipt_download(client):
    admin = make_user("admin_receipt", ADMIN)
    student = make_user("student_receipt", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_token = token_for(client, student.login_id)

    invoice_response = create_invoice(client, admin_token, student.id)
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    payment_response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_token),
    )

    payment = payment_response.get_json()["payment"]
    payment_id = payment["id"]
    order_id = payment["gateway_order_id"]
    transaction_id = "TEST_TXN_001"

    signature = gateways.generate_mock_signature(
        order_id,
        transaction_id,
    )

    confirm_response = client.post(
        f"/api/fees/payments/{payment_id}/confirm",
        headers=auth(student_token),
        json={
            "transaction_id": transaction_id,
            "signature": signature,
        },
    )

    assert confirm_response.status_code == 200
    assert confirm_response.get_json()["payment"]["status"] == "SUCCESS"

    receipt_response = client.get(
        f"/api/fees/payments/{payment_id}/receipt",
        headers=auth(student_token),
    )

    assert receipt_response.status_code == 200
    assert receipt_response.mimetype == "application/pdf"
    assert receipt_response.data.startswith(b"%PDF")


def test_invalid_payment_signature_is_rejected(client):
    admin = make_user("admin_invalid", ADMIN)
    student = make_user("student_invalid", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_token = token_for(client, student.login_id)

    invoice_response = create_invoice(client, admin_token, student.id)
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    payment_response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_token),
    )

    payment_id = payment_response.get_json()["payment"]["id"]

    response = client.post(
        f"/api/fees/payments/{payment_id}/confirm",
        headers=auth(student_token),
        json={
            "transaction_id": "TEST_TXN_BAD",
            "signature": "invalid-signature",
        },
    )

    assert response.status_code == 400

    payment = db.session.get(Payment, payment_id)
    assert payment.status == "PENDING"


def test_duplicate_payment_initiation_is_rejected(client):
    admin = make_user("admin_duplicate", ADMIN)
    student = make_user("student_duplicate", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_token = token_for(client, student.login_id)

    invoice_response = create_invoice(client, admin_token, student.id)
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    first_response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_token),
    )

    second_response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_token),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_student_cannot_download_another_students_receipt(client):
    admin = make_user("admin_private", ADMIN)
    student_one = make_user("student_private_one", STUDENT)
    student_two = make_user("student_private_two", STUDENT)

    admin_token = token_for(client, admin.login_id)
    student_one_token = token_for(client, student_one.login_id)
    student_two_token = token_for(client, student_two.login_id)

    invoice_response = create_invoice(
        client,
        admin_token,
        student_one.id,
    )
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    payment_response = client.post(
        f"/api/fees/invoices/{invoice_id}/pay",
        headers=auth(student_one_token),
    )

    payment = payment_response.get_json()["payment"]
    payment_id = payment["id"]

    transaction_id = "TEST_TXN_PRIVATE"
    signature = gateways.generate_mock_signature(
        payment["gateway_order_id"],
        transaction_id,
    )

    client.post(
        f"/api/fees/payments/{payment_id}/confirm",
        headers=auth(student_one_token),
        json={
            "transaction_id": transaction_id,
            "signature": signature,
        },
    )

    response = client.get(
        f"/api/fees/payments/{payment_id}/receipt",
        headers=auth(student_two_token),
    )

    assert response.status_code == 403


def test_student_cannot_create_fee_invoice(client):
    student = make_user("student_no_invoice", STUDENT)
    student_token = token_for(client, student.login_id)

    response = client.post(
        "/api/fees/invoices",
        headers=auth(student_token),
        json={
            "student_id": student.id,
            "description": "Invalid invoice",
            "amount": "1000.00",
        },
    )

    assert response.status_code == 403