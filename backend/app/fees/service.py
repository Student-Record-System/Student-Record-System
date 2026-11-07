
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

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
from app.fees.models import FeeInvoice, FeeStructure, Payment, FeeReminderLog
from app.enrollment.service import WINDOW_END_KEY
from app.common.notifications import get_notification_client
from app.common.settings import get_setting, set_setting


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


def create_invoice(student_id, description, amount, due_date=None, editor=None):
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
            user_id=editor.id if editor else None,
            login_id=editor.login_id if editor else "SYSTEM",
            details={
                "invoice_number": invoice.invoice_number,
                "student_id": student.id,
                "amount": str(invoice.amount),
                "currency": invoice.currency,
            },
            previous_values=None,
            new_values={
                "status": "UNPAID",
                "amount": str(invoice.amount),
            },
        )

        repository.commit()
        return invoice

    except Exception:
        repository.rollback()
        raise


def _semester(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8:
        raise ValidationError("semester must be an integer between 1 and 8.")
    return value


def _program(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("program is required.")
    return value.strip()


def create_fee_structure(program, semester, amount, course_code=None):
    program = _program(program)
    semester = _semester(semester)

    if course_code is not None:
        if not isinstance(course_code, str) or not course_code.strip():
            raise ValidationError("course_code must be non-empty when provided.")
        course_code = course_code.strip().upper()

    structure = FeeStructure(
        program=program,
        semester=semester,
        course_code=course_code,
        amount=_money(amount),
        currency="INR",
    )

    if repository.get_fee_structure(program, semester, course_code) is not None:
        raise ConflictError("This fee structure already exists.")

    try:
        repository.add_fee_structure(structure)
    except IntegrityError as exc:
        repository.rollback()
        raise ConflictError("This fee structure already exists.") from exc

    return structure


def get_fee_structures():
    return repository.get_fee_structures()


def _fees_for_enrollments(profile, enrollments):
    course_structures = [
        repository.get_fee_structure(
            profile.program,
            enrollment.semester,
            enrollment.course_code,
        )
        for enrollment in enrollments
    ]

    if all(structure is not None for structure in course_structures):
        return course_structures

    program_structure = repository.get_fee_structure(
        profile.program,
        enrollments[0].semester,
    )

    return [program_structure] if program_structure is not None else []


def generate_invoices(editor=None):
    window_end = get_setting(WINDOW_END_KEY)

    if window_end is None:
        raise ConflictError("The enrollment window is not configured.")

    try:
        closed_at = datetime.fromisoformat(window_end)
    except ValueError as exc:
        raise ConflictError("The enrollment window configuration is invalid.") from exc

    now = Clock.now()

    if now <= closed_at:
        raise ConflictError("The enrollment window is still open.")

    if now > closed_at + timedelta(hours=24):
        raise ConflictError("The invoice-generation window has expired.")

    grouped = {}

    for user, profile, enrollment in repository.enrolled_student_records():
        grouped.setdefault((user, profile, enrollment.semester), []).append(enrollment)

    pending = []

    for (user, profile, semester), enrollments in grouped.items():
        generation_key = f"{window_end}:{user.id}:{semester}"

        if repository.get_generated_invoice(generation_key) is not None:
            continue

        structures = _fees_for_enrollments(profile, enrollments)

        if not structures:
            raise ValidationError(
                f"No fee structure is configured for {profile.program}, "
                f"semester {semester}."
            )

        amount = sum(
            (structure.amount for structure in structures),
            Decimal("0.00"),
        )

        invoice = FeeInvoice(
            invoice_number=f"INV-{uuid4().hex[:12].upper()}",
            student_id=user.id,
            description=f"Semester {semester} fee invoice",
            amount=amount,
            currency="INR",
            semester=semester,
            generation_key=generation_key,
            status="UNPAID",
        )

        pending.append((invoice, profile))

    try:
        for invoice, profile in pending:
            db.session.add(invoice)

            record_event(
                event_type="FEE_INVOICE_CREATED",
                user_id=editor.id if editor else None,
                login_id=editor.login_id if editor else "SYSTEM",
                details={
                    "invoice_number": invoice.invoice_number,
                    "student_id": invoice.student_id,
                    "semester": invoice.semester,
                    "amount": str(invoice.amount),
                    "currency": invoice.currency,
                    "generated": True,
                },
                profile_id=profile.id,
                previous_values=None,
                new_values={
                    "status": "UNPAID",
                    "amount": str(invoice.amount),
                },
            )

        repository.commit()

    except Exception:
        repository.rollback()
        raise

    return [invoice for invoice, _ in pending]


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

        student = _student_user(student_id)

        record_event(
            event_type="FEE_PAYMENT_INITIATED",
            user_id=student.id,
            login_id=student.login_id,
            details={
                "invoice_number": invoice.invoice_number,
                "payment_id": payment.id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
            previous_values=None,
            new_values={"status": "PENDING"},
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

    student = _student_user(student_id)

    return _confirm_successful_payment(
        payment,
        transaction_id,
        signature,
        actor=student,
    )


def confirm_payment_callback(order_id, transaction_id, signature):
    payment = repository.get_payment_by_order_id(order_id)

    if not payment:
        raise NotFoundError("Payment not found.")

    return _confirm_successful_payment(
        payment,
        transaction_id,
        signature,
        actor_login_id="PAYMENT_GATEWAY",
    )


def _confirm_successful_payment(
    payment,
    transaction_id,
    signature,
    actor=None,
    actor_login_id=None,
):
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
            user_id=actor.id if actor else None,
            login_id=actor.login_id if actor else actor_login_id,
            details={
                "invoice_number": invoice.invoice_number,
                "student_id": payment.student_id,
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number,
                "transaction_id": transaction_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
            previous_values={
                "payment_status": "PENDING",
                "invoice_status": "UNPAID",
            },
            new_values={
                "payment_status": "SUCCESS",
                "invoice_status": "PAID",
            },
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


FEE_REMINDER_DAYS_KEY = "fee_reminder_days_before_due"
DEFAULT_FEE_REMINDER_DAYS = 3


def get_fee_reminder_settings():
    value = get_setting(
        FEE_REMINDER_DAYS_KEY,
        str(DEFAULT_FEE_REMINDER_DAYS),
    )

    return {
        "days_before_due": int(value),
    }


def configure_fee_reminders(days_before_due):
    if (
        isinstance(days_before_due, bool)
        or not isinstance(days_before_due, int)
        or not 0 <= days_before_due <= 30
    ):
        raise ValidationError(
            "days_before_due must be an integer between 0 and 30."
        )

    set_setting(FEE_REMINDER_DAYS_KEY, str(days_before_due))

    return {
        "days_before_due": days_before_due,
    }


def send_scheduled_fee_reminders():
    settings = get_fee_reminder_settings()
    days_before_due = settings["days_before_due"]

    target_date = Clock.now().date() + timedelta(
        days=days_before_due
    )

    invoices = repository.get_invoices_due_on(target_date)

    notification_client = get_notification_client()
    sent_count = 0
    skipped_count = 0

    for invoice in invoices:
        # Recheck the status before dispatching.
        if invoice.status != "UNPAID":
            skipped_count += 1
            continue

        existing = repository.get_fee_reminder(
            invoice.id,
            invoice.due_date,
            days_before_due,
        )

        if existing is not None:
            skipped_count += 1
            continue

        student = invoice.student

        subject = "Fee Payment Reminder"

        body = (
            f"Dear {student.login_id}, "
            f"your fee payment of {invoice.currency} "
            f"{invoice.amount} for invoice "
            f"{invoice.invoice_number} is due on "
            f"{invoice.due_date.isoformat()}. "
            f"Please complete your payment."
        )

        try:
            notification_client.send(
                recipient=student.login_id,
                subject=subject,
                body=body,
                kind="FEE_REMINDER",
            )

            repository.create_fee_reminder(
                FeeReminderLog(
                    invoice_id=invoice.id,
                    due_date=invoice.due_date,
                    days_before_due=days_before_due,
                )
            )

            repository.commit()
            sent_count += 1

        except Exception:
            repository.rollback()
            raise

    return {
        "target_date": target_date.isoformat(),
        "days_before_due": days_before_due,
        "sent_count": sent_count,
        "skipped_count": skipped_count,
    }
