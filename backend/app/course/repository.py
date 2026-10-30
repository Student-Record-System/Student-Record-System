from app.auth.models import User
from app.course.models import Course
from app.enrollment.models import ENROLLED, Enrollment
from app.extensions import db
from app.profile.models import StudentProfile


def get_by_code(code):
    return db.session.execute(
        db.select(Course).filter_by(code=code)
    ).scalar_one_or_none()


def add(course):
    db.session.add(course)
    db.session.commit()
    return course


def list_all():
    return db.session.execute(
        db.select(Course).order_by(Course.semester, Course.code)
    ).scalars().all()


def get_user_by_login_id(login_id):
    return db.session.execute(
        db.select(User).filter_by(login_id=login_id)
    ).scalar_one_or_none()


def assign_faculty(course, faculty):
    course.faculty_id = faculty.id
    db.session.commit()
    return course


def get_course_roster(course_code):
    return db.session.execute(
        db.select(Enrollment, StudentProfile)
        .join(
            StudentProfile,
            StudentProfile.srn == Enrollment.srn,
        )
        .where(
            Enrollment.course_code == course_code,
            Enrollment.status == ENROLLED,
        )
        .order_by(StudentProfile.srn)
    ).all()