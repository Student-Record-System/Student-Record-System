from app.course.models import Course
from app.extensions import db


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
