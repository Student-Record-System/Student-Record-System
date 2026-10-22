from app.common.clock import Clock
from app.extensions import db


class NotificationOutbox(db.Model):
    """Messages the mock notification service 'sent'. Dev and test only (SAD D4)."""
    __tablename__ = "notification_outbox"

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="sent")
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)