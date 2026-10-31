from decimal import Decimal

from app.common.clock import Clock
from app.extensions import db


class FeeInvoice(db.Model):
    __tablename__ = "fee_invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=False)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")

    status = db.Column(db.String(20), nullable=False, default="UNPAID")
    due_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=Clock.now,
        onupdate=Clock.now,
    )

    student = db.relationship("User", backref="fee_invoices")
    payments = db.relationship(
        "Payment",
        backref="invoice",
        lazy=True,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="check_fee_invoice_amount_positive"),
        db.CheckConstraint(
            "status IN ('UNPAID', 'PAID', 'CANCELLED')",
            name="check_fee_invoice_status",
        ),
    )


class Payment(db.Model):
    __tablename__ = "fee_payments"

    id = db.Column(db.Integer, primary_key=True)

    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("fee_invoices.id"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")

    status = db.Column(db.String(20), nullable=False, default="PENDING")

    gateway = db.Column(db.String(40), nullable=False, default="MOCK")
    gateway_order_id = db.Column(db.String(100), unique=True, nullable=False)
    gateway_transaction_id = db.Column(db.String(100), unique=True, nullable=True)

    receipt_number = db.Column(db.String(40), unique=True, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)
    paid_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("User", backref="fee_payments")

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="check_payment_amount_positive"),
        db.CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED')",
            name="check_payment_status",
        ),
    )