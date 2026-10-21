import os

from app import create_app
from app.auth import repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN
from app.extensions import db

flask_app = create_app()

with flask_app.app_context():
    db.create_all()
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Set SEED_ADMIN_PASSWORD in your .env file first.")
    if repository.get_user_by_login_id("admin") is None:
        repository.add_user(User(
            login_id="admin",
            email="admin@example.com",
            password_hash=hash_password(password),
            role=ADMIN,
        ))
        print("Created admin account (login ID: admin).")
    else:
        print("Admin account already exists.")