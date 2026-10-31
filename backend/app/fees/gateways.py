import hashlib
import hmac

from flask import current_app


def _get_secret():
    return current_app.config.get(
        "PAYMENT_GATEWAY_SECRET",
        "development-only-secret-change-before-production",
    )


def create_order(payment_id, amount, currency, order_id):
    return {
        "order_id": order_id,
        "payment_id": payment_id,
        "amount": str(amount),
        "currency": currency,
        "gateway": "MOCK",
    }


def generate_mock_signature(order_id, transaction_id):
    message = f"{order_id}|{transaction_id}".encode("utf-8")

    return hmac.new(
        _get_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_payment(order_id, transaction_id, signature):
    if not order_id or not transaction_id or not signature:
        return False

    expected_signature = generate_mock_signature(
        order_id,
        transaction_id,
    )

    return hmac.compare_digest(expected_signature, signature)