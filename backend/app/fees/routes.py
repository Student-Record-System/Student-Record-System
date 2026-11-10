from datetime import date

from flask import Blueprint, jsonify, request, send_file

from app.auth.access import current_user, roles_required
from app.auth.models import User
from app.common.errors import ValidationError
from app.common.roles import ADMIN, STUDENT
from app.enrollment import service as enrollment_service
from app.fees import service
from app.fees.pdf import generate_receipt

bp = Blueprint("fees", __name__, url_prefix="/api")


def _user_id():
    return current_user().id


# ---- JSON serializers ----

def _invoice_json(invoice):
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "student_id": invoice.student_id,
        "description": invoice.description,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "semester": invoice.semester,
        "status": invoice.status,
        "due_date": (
            invoice.due_date.isoformat()
            if invoice.due_date
            else None
        ),
        "created_at": invoice.created_at.isoformat(),
    }


def _structure_json(structure):
    return {
        "id": structure.id,
        "program": structure.program,
        "semester": structure.semester,
        "course_code": structure.course_code,
        "amount": str(structure.amount),
        "currency": structure.currency,
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
        "paid_at": (
            payment.paid_at.isoformat()
            if payment.paid_at
            else None
        ),
    }


def _fee_override_json(override):
    return {
        "id": override.id,
        "student_id": override.student_id,
        "student_srn": override.student.login_id,
        "semester": override.semester,
        "admin_user_id": override.admin_user_id,
        "reason": override.reason,
        "created_at": override.created_at.isoformat(),
    }


# ---- fee structures ----

@bp.post("/fees/structures")
@roles_required(ADMIN)
def create_fee_structure():
    data = request.get_json(silent=True) or {}

    structure = service.create_fee_structure(
        program=data.get("program"),
        semester=data.get("semester"),
        amount=data.get("amount"),
        course_code=data.get("course_code"),
    )

    return jsonify({
        "message": "Fee structure configured successfully.",
        "fee_structure": _structure_json(structure),
    }), 201


@bp.get("/fees/structures")
@roles_required(ADMIN)
def list_fee_structures():
    return jsonify({
        "fee_structures": [
            _structure_json(structure)
            for structure in service.get_fee_structures()
        ]
    }), 200


# ---- invoice generation and management ----

@bp.post("/fees/invoices/generate")
@roles_required(ADMIN)
def generate_invoices():
    invoices = service.generate_invoices(editor=current_user())

    return jsonify({
        "message": "Fee invoices generated successfully.",
        "invoices": [
            _invoice_json(invoice)
            for invoice in invoices
        ],
    }), 201


@bp.post("/fees/invoices")
@roles_required(ADMIN)
def create_invoice():
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    description = data.get("description")
    amount = data.get("amount")
    due_date_value = data.get("due_date")

    if (
        not isinstance(student_id, int)
        or isinstance(student_id, bool)
    ):
        raise ValidationError(
            "A valid student_id is required."
        )

    due_date = None

    if due_date_value:
        try:
            due_date = date.fromisoformat(due_date_value)
        except (TypeError, ValueError):
            raise ValidationError(
                "due_date must use YYYY-MM-DD format."
            )

    invoice = service.create_invoice(
        student_id=student_id,
        description=description,
        amount=amount,
        due_date=due_date,
        editor=current_user(),
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
        "invoices": [
            _invoice_json(invoice)
            for invoice in invoices
        ]
    }), 200


# ---- payments ----

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


@bp.post("/fees/payments/callback")
def payment_callback():
    data = request.get_json(silent=True) or {}

    payment = service.confirm_payment_callback(
        order_id=data.get("order_id"),
        transaction_id=data.get("transaction_id"),
        signature=data.get("signature"),
    )

    return jsonify({
        "message": "Payment callback processed successfully.",
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
        raise ValidationError(
            "A receipt is available only after successful payment."
        )

    pdf_buffer = generate_receipt(payment)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{payment.receipt_number}.pdf",
    )


# ---- fee reminder settings ----

@bp.get("/fees/reminder-settings")
@roles_required(ADMIN)
def get_reminder_settings():
    return jsonify({
        "reminder_settings": service.get_fee_reminder_settings()
    }), 200


@bp.put("/fees/reminder-settings")
@roles_required(ADMIN)
def update_reminder_settings():
    data = request.get_json(silent=True) or {}

    if "days_before_due" not in data:
        raise ValidationError(
            "days_before_due is required."
        )

    settings = service.configure_fee_reminders(
        data["days_before_due"]
    )

    return jsonify({
        "message": "Fee reminder settings updated successfully.",
        "reminder_settings": settings,
    }), 200


# ---- fee enrollment threshold ----

@bp.get("/fees/enrollment-threshold")
@roles_required(ADMIN)
def get_enrollment_threshold():
    threshold = (
        enrollment_service.get_fee_enrollment_threshold()
    )

    return jsonify({
        "threshold": str(threshold),
        "currency": "INR",
    }), 200


@bp.put("/fees/enrollment-threshold")
@roles_required(ADMIN)
def update_enrollment_threshold():
    data = request.get_json(silent=True) or {}

    if "threshold" not in data:
        raise ValidationError(
            "threshold is required."
        )

    result = enrollment_service.set_fee_enrollment_threshold(
        data["threshold"]
    )

    return jsonify({
        "message": (
            "Fee enrollment threshold updated successfully."
        ),
        "threshold": result["threshold"],
        "currency": "INR",
    }), 200


# ---- fee enrollment overrides ----

@bp.post("/fees/enrollment-overrides")
@roles_required(ADMIN)
def create_enrollment_override():
    data = request.get_json(silent=True) or {}

    override = service.create_fee_enrollment_override(
        student_srn=data.get("student_srn"),
        semester=data.get("semester"),
        reason=data.get("reason"),
        admin_user_id=_user_id(),
    )

    return jsonify({
        "message": (
            "Enrollment override recorded successfully."
        ),
        "override": _fee_override_json(override),
    }), 201


@bp.get("/fees/enrollment-overrides")
@roles_required(ADMIN)
def list_enrollment_overrides():
    student_srn = request.args.get("student_srn")
    student_id = None

    if student_srn:
        student = User.query.filter_by(
            login_id=student_srn.strip()
        ).first()

        if student is None:
            raise ValidationError("Student not found.")

        student_id = student.id

    overrides = service.get_fee_enrollment_overrides(
        student_id
    )

    return jsonify({
        "overrides": [
            _fee_override_json(override)
            for override in overrides
        ]
    }), 200