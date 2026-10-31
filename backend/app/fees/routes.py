from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.auth.access import current_user, roles_required
from app.common.errors import ValidationError
from app.common.roles import ADMIN, STUDENT
from app.fees import repository, service
from app.fees.pdf import generate_receipt

bp = Blueprint("fees", __name__, url_prefix="/api")


def _user_id():
    user = current_user()
    return user.id


def _invoice_json(invoice):
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "student_id": invoice.student_id,
        "description": invoice.description,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "status": invoice.status,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "created_at": invoice.created_at.isoformat(),
    }


def _payment_json(payment):
    return {
        "id": payment.id,
        "invoice_id": payment.invoice_id,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "gateway": payment.gateway,
        "gateway_order_id": payment.gateway_order_id,
        "gateway_transaction_id": payment.gateway_transaction_id,
        "receipt_number": payment.receipt_number,
        "created_at": payment.created_at.isoformat(),
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
    }


@bp.post("/fees/invoices")
@roles_required(ADMIN)
def create_invoice():
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    description = data.get("description")
    amount = data.get("amount")
    due_date_value = data.get("due_date")

    if not isinstance(student_id, int) or isinstance(student_id, bool):
        raise ValidationError("A valid student_id is required.")

    due_date = None
    if due_date_value:
        try:
            due_date = date.fromisoformat(due_date_value)
        except (TypeError, ValueError):
            raise ValidationError("due_date must use YYYY-MM-DD format.")

    invoice = service.create_invoice(
        student_id=student_id,
        description=description,
        amount=amount,
        due_date=due_date,
    )

    return jsonify({
        "message": "Fee invoice created successfully.",
        "invoice": _invoice_json(invoice),
    }), 201


@bp.get("/fees/invoices")
@roles_required(STUDENT)
def list_invoices():
    invoices = service.get_student_invoices(_user_id())

    return jsonify({
        "invoices": [_invoice_json(invoice) for invoice in invoices]
    }), 200


@bp.post("/fees/invoices/<int:invoice_id>/pay")
@roles_required(STUDENT)
def initiate_payment(invoice_id):
    result = service.initiate_payment(
        invoice_id=invoice_id,
        student_id=_user_id(),
    )

    return jsonify({
        "message": "Payment initiated successfully.",
        "payment": _payment_json(result["payment"]),
        "gateway_order": result["gateway_order"],
    }), 201


@bp.post("/fees/payments/<int:payment_id>/confirm")
@roles_required(STUDENT)
def confirm_payment(payment_id):
    data = request.get_json(silent=True) or {}

    payment = service.confirm_payment(
        payment_id=payment_id,
        student_id=_user_id(),
        transaction_id=data.get("transaction_id"),
        signature=data.get("signature"),
    )

    return jsonify({
        "message": "Payment confirmed successfully.",
        "payment": _payment_json(payment),
    }), 200


@bp.get("/fees/payments/<int:payment_id>/receipt")
@roles_required(STUDENT)
def download_receipt(payment_id):
    payment = service.get_payment(
        payment_id=payment_id,
        student_id=_user_id(),
    )

    if payment.status != "SUCCESS":
        raise ValidationError("A receipt is available only after successful payment.")

    pdf_buffer = generate_receipt(payment)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{payment.receipt_number}.pdf",
    )