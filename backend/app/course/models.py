from app.common.clock import Clock
from app.extensions import db


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    department = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=Clock.now)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=Clock.now, onupdate=Clock.now
    )
