from app.common.clock import Clock
from app.extensions import db


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    srn = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(30), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    emergency_contact_name = db.Column(db.String(150), nullable=True)
    emergency_contact_phone = db.Column(db.String(30), nullable=True)
    program = db.Column(db.String(120), nullable=False)
    branch = db.Column(db.String(120), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=Clock.now, onupdate=Clock.now
    )


class ProfileChangeRequest(db.Model):
    __tablename__ = "profile_change_requests"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(
        db.Integer, db.ForeignKey("student_profiles.id"), nullable=False
    )
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    emergency_contact_name = db.Column(db.String(150), nullable=True)
    emergency_contact_phone = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Pending Verification")
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)
