import logging

from app.common.models import NotificationOutbox
from app.extensions import db

log = logging.getLogger(__name__)


class NotificationClient:
    """Mock of the external Notification Service (SAD D4).
    A real email or SMS client would replace this class and keep the same send() method."""

    def send(self, recipient, subject, body, kind):
        entry = NotificationOutbox(
            recipient=recipient, subject=subject, body=body, kind=kind, status="sent"
        )
        db.session.add(entry)
        db.session.commit()
        log.info("Notification %s sent to %s", kind, recipient)  # never log the body
        return entry


def get_notification_client():
    return NotificationClient()