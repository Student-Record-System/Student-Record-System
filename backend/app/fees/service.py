from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.auth.models import User
from app.common.audit import record_event
from app.common.clock import Clock
from app.common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.roles import STUDENT
from app.extensions import db
from app.fees import gateways, repository
from app.fees.models import FeeInvoice, Payment


def _money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Amount must be a valid number.")

    if not amount.is_finite() or amount <= 0:
        raise ValidationError("Amount must be greater than zero.")

    return amount.quantize(Decimal("0.01"))


def _student_user(student_id):
    user = db.session.get(User, student_id)

    if not user or user.role != STUDENT or not user.is_active:
        raise ValidationError("The specified student does not exist.")

    return user


def create_invoice(student_id, description, amount, due_date=None):
    student = _student_user(student_id)

    if not isinstance(description, str) or not description.strip():
        raise ValidationError("Invoice description is required.")

    invoice = FeeInvoice(
        invoice_number=f"INV-{uuid4().hex[:12].upper()}",
        student_id=student.id,
        description=description.strip(),
        amount=_money(amount),
        currency="INR",
        status="UNPAID",
        due_date=due_date,
    )

    try:
        repository.create_invoice(invoice)

        record_event(
            event_type="FEE_INVOICE_CREATED",
            details={
                "invoice_number": invoice.invoice_number,
                "amount": str(invoice.amount),
                "currency": invoice.currency,
            },
            profile_id=student.id,
        )

        repository.commit()
        return invoice

    except Exception:
        repository.rollback()
        raise


def get_student_invoices(student_id):
    return repository.get_student_invoices(student_id)


def initiate_payment(invoice_id, student_id):
    invoice = repository.get_invoice_by_id(invoice_id)

    if not invoice:
        raise NotFoundError("Invoice not found.")

    if invoice.student_id != student_id:
        raise ForbiddenError("You cannot pay another student's invoice.")

    if invoice.status == "PAID":
        raise ConflictError("This invoice has already been paid.")

    if invoice.status != "UNPAID":
        raise ConflictError("This invoice cannot be paid.")

    existing_payments = repository.get_payments_for_invoice(invoice.id)

    if any(payment.status == "PENDING" for payment in existing_payments):
        raise ConflictError("A payment is already pending for this invoice.")

    payment = Payment(
        invoice_id=invoice.id,
        student_id=student_id,
        amount=invoice.amount,
        currency=invoice.currency,
        status="PENDING",
        gateway="MOCK",
        gateway_order_id=f"MOCK_ORDER_{uuid4().hex.upper()}",
    )

    try:
        repository.create_payment(payment)

        record_event(
            event_type="FEE_PAYMENT_INITIATED",
            details={
                "invoice_number": invoice.invoice_number,
                "payment_id": payment.id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
            profile_id=student_id,
        )

        repository.commit()

        gateway_order = gateways.create_order(
            payment.id,
            payment.amount,
            payment.currency,
            payment.gateway_order_id,
        )

        return {
            "payment": payment,
            "gateway_order": gateway_order,
        }

    except Exception:
        repository.rollback()
        raise


def confirm_payment(payment_id, student_id, transaction_id, signature):
    payment = repository.get_payment_by_id(payment_id)

    if not payment:
        raise NotFoundError("Payment not found.")

    if payment.student_id != student_id:
        raise ForbiddenError("You cannot confirm another student's payment.")

    if payment.status == "SUCCESS":
        if payment.gateway_transaction_id == transaction_id:
            return payment

        raise ConflictError("This payment has already been completed.")

    if payment.status != "PENDING":
        raise ConflictError("This payment is not pending.")

    if not transaction_id or not isinstance(transaction_id, str):
        raise ValidationError("A transaction ID is required.")

    if repository.get_payment_by_transaction_id(transaction_id):
        raise ConflictError("This transaction ID has already been used.")

    if not gateways.verify_payment(
        payment.gateway_order_id,
        transaction_id,
        signature,
    ):
        raise ValidationError("Payment verification failed.")

    invoice = repository.get_invoice_by_id(payment.invoice_id)

    if not invoice or invoice.status != "UNPAID":
        raise ConflictError("The invoice is no longer payable.")

    try:
        payment.status = "SUCCESS"
        payment.gateway_transaction_id = transaction_id
        payment.paid_at = Clock.now()
        payment.receipt_number = f"REC-{uuid4().hex[:12].upper()}"

        invoice.status = "PAID"

        record_event(
            event_type="FEE_PAYMENT_SUCCESS",
            details={
                "invoice_number": invoice.invoice_number,
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number,
                "transaction_id": transaction_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
            profile_id=student_id,
        )

        repository.commit()
        return payment

    except Exception:
        repository.rollback()
        raise


def get_payment(payment_id, student_id):
    payment = repository.get_payment_by_id(payment_id)

    if not payment:
        raise NotFoundError("Payment not found.")

    if payment.student_id != student_id:
        raise ForbiddenError("You cannot access another student's payment.")

    return payment