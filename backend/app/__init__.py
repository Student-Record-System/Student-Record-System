import importlib
import importlib.util

from flask import Flask

from app.common.errors import register_error_handlers
from app.config import Config
from app.extensions import db, jwt

# One folder per module (SAD 4.1). A module is picked up automatically
# if app/<name>/routes.py exists and defines a Blueprint called bp.
MODULES = [
    "health",
    "auth",
    "profile",
    "enrollment",
    "attendance",
    "grades",
    "fees",
    "reports",
    "admin",
    "course",
    "reviews",
]


def register_modules(app):
    for name in MODULES:
        if importlib.util.find_spec(f"app.{name}") is None:
            continue

        if importlib.util.find_spec(f"app.{name}.routes") is None:
            continue

        app.register_blueprint(
            importlib.import_module(f"app.{name}.routes").bp
        )


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    missing = [
        key
        for key in ("SQLALCHEMY_DATABASE_URI", "JWT_SECRET_KEY")
        if not app.config.get(key)
    ]

    if missing:
        raise RuntimeError(
            f"Missing settings: {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in."
        )

    db.init_app(app)
    jwt.init_app(app)

    register_error_handlers(app)
    register_modules(app)

    @app.cli.command("send-fee-reminders")
    def send_fee_reminders_command():
        """Send scheduled reminders for unpaid fee invoices."""
        from app.fees.service import send_scheduled_fee_reminders

        result = send_scheduled_fee_reminders()
        print(result)

    @app.cli.command("archive-audit-events")
    def archive_audit_events_command():
        """Archive audit events older than five years."""
        from app.common.audit import archive_old_events

        result = archive_old_events()
        print(result)

    return app