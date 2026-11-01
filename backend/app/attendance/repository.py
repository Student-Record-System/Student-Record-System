from sqlalchemy.exc import IntegrityError

from app.attendance.models import Attendance
from app.extensions import db


def get_attendance(srn, course_code, attendance_date, session):
    return db.session.execute(
        db.select(Attendance).filter_by(
            srn=srn,
            course_code=course_code,
            attendance_date=attendance_date,
            session=session,
        )
    ).scalar_one_or_none()


def add_all(records):
    db.session.add_all(records)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise

    return records


def list_for_course_session(course_code, attendance_date, session):
    return db.session.execute(
        db.select(Attendance)
        .filter_by(
            course_code=course_code,
            attendance_date=attendance_date,
            session=session,
        )
        .order_by(Attendance.srn)
    ).scalars().all()
