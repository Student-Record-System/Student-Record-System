from app.fees.models import FeeInvoice, Payment
from app.extensions import db


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