from app.common.clock import Clock
from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.String(50), unique=True, nullable=False)  # SRN or employee ID
    email = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)  # used by STU-F-003
    locked_until = db.Column(db.DateTime, nullable=True)                # used by STU-F-003
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)