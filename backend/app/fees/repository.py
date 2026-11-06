
from app.auth.models import User
from app.common.roles import STUDENT
from app.extensions import db
from app.enrollment.models import ENROLLED, Enrollment
from app.fees.models import (
    FeeInvoice,
    FeeStructure,
    Payment,
    FeeReminderLog,
)
from app.profile.models import StudentProfile


def create_invoice(invoice):
    db.session.add(invoice)
    db.session.flush()
    return invoice


def get_invoice_by_id(invoice_id):
    return db.session.get(FeeInvoice, invoice_id)


def get_invoice_by_number(invoice_number):
    return FeeInvoice.query.filter_by(
        invoice_number=invoice_number
    ).first()


def get_student_invoices(student_id):
    return (
        FeeInvoice.query
        .filter_by(student_id=student_id)
        .order_by(FeeInvoice.created_at.desc())
        .all()
    )


def get_fee_structure(program, semester, course_code=None):
    return FeeStructure.query.filter_by(
        program=program,
        semester=semester,
        course_code=course_code,
    ).first()


def add_fee_structure(structure):
    db.session.add(structure)
    db.session.commit()
    return structure


def get_fee_structures():
    return FeeStructure.query.order_by(
        FeeStructure.program,
        FeeStructure.semester,
        FeeStructure.course_code,
    ).all()


def enrolled_student_records():
    return (
        db.session.query(User, StudentProfile, Enrollment)
        .join(StudentProfile, StudentProfile.srn == User.login_id)
        .join(Enrollment, Enrollment.srn == StudentProfile.srn)
        .filter(
            User.role == STUDENT,
            User.is_active.is_(True),
            Enrollment.status == ENROLLED,
        )
        .order_by(User.id, Enrollment.semester, Enrollment.course_code)
        .all()
    )


def get_generated_invoice(generation_key):
    return FeeInvoice.query.filter_by(
        generation_key=generation_key
    ).first()


def create_payment(payment):
    db.session.add(payment)
    db.session.flush()
    return payment


def get_payment_by_id(payment_id):
    return db.session.get(Payment, payment_id)


def get_payment_by_order_id(order_id):
    return Payment.query.filter_by(
        gateway_order_id=order_id
    ).first()


def get_payment_by_transaction_id(transaction_id):
    return Payment.query.filter_by(
        gateway_transaction_id=transaction_id
    ).first()


def get_payments_for_invoice(invoice_id):
    return (
        Payment.query
        .filter_by(invoice_id=invoice_id)
        .order_by(Payment.created_at.desc())
        .all()
    )


def commit():
    db.session.commit()


def rollback():
    db.session.rollback()


# Fee reminder functions

def get_invoices_due_on(target_date):
    return (
        FeeInvoice.query
        .filter(
            FeeInvoice.status == "UNPAID",
            FeeInvoice.due_date == target_date,
        )
        .order_by(FeeInvoice.id)
        .all()
    )


def get_fee_reminder(invoice_id, due_date, days_before_due):
    return FeeReminderLog.query.filter_by(
        invoice_id=invoice_id,
        due_date=due_date,
        days_before_due=days_before_due,
    ).first()


def create_fee_reminder(reminder):
    db.session.add(reminder)
    db.session.flush()
    return reminder
