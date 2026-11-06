from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError

from app.attendance.models import Attendance
from app.enrollment.models import COMPLETED, ENROLLED, Enrollment
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

def attendance_summary_for_course(course_code):
    return db.session.execute(
        db.select(
            Enrollment.srn,
            func.coalesce(
                func.sum(
                    case((Attendance.status == "Present", 1), else_=0)
                ),
                0,
            ).label("present_sessions"),
            func.count(Attendance.id).label("total_sessions"),
        )
        .outerjoin(
            Attendance,
            (Attendance.srn == Enrollment.srn)
            & (Attendance.course_code == Enrollment.course_code),
        )
        .where(
            Enrollment.course_code == course_code,
            Enrollment.status.in_((ENROLLED, COMPLETED)),
        )
        .group_by(Enrollment.srn)
        .order_by(Enrollment.srn)
    ).all()


def attendance_summary_for_student(srn):
    return db.session.execute(
        db.select(
            Enrollment.course_code,
            func.coalesce(
                func.sum(
                    case((Attendance.status == "Present", 1), else_=0)
                ),
                0,
            ).label("present_sessions"),
            func.count(Attendance.id).label("total_sessions"),
        )
        .outerjoin(
            Attendance,
            (Attendance.srn == Enrollment.srn)
            & (Attendance.course_code == Enrollment.course_code),
        )
        .where(
            Enrollment.srn == srn,
            Enrollment.status.in_((ENROLLED, COMPLETED)),
        )
        .group_by(Enrollment.course_code)
        .order_by(Enrollment.course_code)
    ).all()


def attendance_counts_for_student_course(srn, course_code):
    present_sessions, total_sessions = db.session.execute(
        db.select(
            func.coalesce(
                func.sum(
                    case((Attendance.status == "Present", 1), else_=0)
                ),
                0,
            ),
            func.count(Attendance.id),
        ).where(
            Attendance.srn == srn,
            Attendance.course_code == course_code,
        )
    ).one()
    return present_sessions, total_sessions
def attendance_records_for_student(srn):
    return db.session.execute(
        db.select(
            Enrollment.course_code,
            Attendance.attendance_date,
            Attendance.session,
            Attendance.status,
        )
        .outerjoin(
            Attendance,
            (Attendance.srn == Enrollment.srn)
            & (Attendance.course_code == Enrollment.course_code),
        )
        .where(
            Enrollment.srn == srn,
            Enrollment.status.in_((ENROLLED, COMPLETED)),
        )
        .order_by(
            Enrollment.course_code,
            Attendance.attendance_date,
            Attendance.session,
        )
    ).all()