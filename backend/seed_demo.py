"""Creates demo data so the app can be tried by hand and measured (STU-NF-001):
one student account and profile, three courses, and published results.

Run from backend/ after seed.py:   python seed_demo.py
The student's password comes from SEED_DEMO_PASSWORD in your .env file
(or you are asked for it). Safe to run more than once.
"""
import os
from datetime import date
from getpass import getpass

from app import create_app
from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import STUDENT
from app.course.models import Course
from app.enrollment.models import COMPLETED, Enrollment
from app.extensions import db
from app.grades.models import StudentMark
from app.profile.models import StudentProfile

SRN = "PES2UG24CS000"
COURSES = [
    # code, title, credits, semester, internal marks, end-semester marks
    ("CS101", "Programming in Python", 4, 1, 88, 92),
    ("CS102", "Discrete Mathematics", 3, 1, 74, 70),
    ("CS201", "Data Structures", 4, 2, 81, 85),
]


def get_or_create(model, lookup, **values):
    row = db.session.execute(db.select(model).filter_by(**lookup)).scalar_one_or_none()
    if row is None:
        row = model(**lookup, **values)
        db.session.add(row)
    return row


flask_app = create_app()

with flask_app.app_context():
    db.create_all()
    admin = auth_repository.get_user_by_login_id("admin")
    if admin is None:
        raise SystemExit("Run seed.py first: it creates the admin account.")

    if auth_repository.get_user_by_login_id(SRN) is None:
        password = os.environ.get("SEED_DEMO_PASSWORD") or getpass("Demo student password: ")
        if not password:
            raise SystemExit("A password is required.")
        auth_repository.add_user(User(
            login_id=SRN, email="demo.student@example.com",
            password_hash=hash_password(password), role=STUDENT,
        ))

    get_or_create(
        StudentProfile, {"srn": SRN},
        full_name="Demo Student", email="demo.student@example.com",
        phone="9876543210", date_of_birth=date(2005, 1, 1), gender="Female",
        program="B.Tech", branch="Computer Science", semester=3,
    )
    for code, title, credits, semester, internal, end_sem in COURSES:
        get_or_create(
            Course, {"code": code},
            title=title, credits=credits, semester=semester, department="Computer Science",
        )
        get_or_create(
            Enrollment, {"srn": SRN, "course_code": code},
            semester=semester, status=COMPLETED,
        )
        get_or_create(
            StudentMark, {"course_code": code, "srn": SRN},
            internal_marks=internal, end_semester_marks=end_sem,
            status="Approved", submitted_by=admin.id,
        )
    db.session.commit()
    print(f"Demo student ready. Log in with ID {SRN}.")