from app.extensions import db
from app.grades.models import PENDING_APPROVAL, StudentMark
from app.course.models import Course

def get_mark(course_code, srn):
    return db.session.execute(
        db.select(StudentMark).filter_by(
            course_code=course_code,
            srn=srn,
        )
    ).scalar_one_or_none()


def add_mark(mark):
    db.session.add(mark)
    db.session.commit()
    return mark


def get_pending_marks():
    return db.session.execute(
        db.select(StudentMark)
        .filter_by(status=PENDING_APPROVAL)
        .order_by(StudentMark.course_code, StudentMark.srn)
    ).scalars().all()


def get_student_approved_marks(srn):
    return db.session.execute(
        db.select(StudentMark)
        .filter_by(srn=srn, status="Approved")
        .order_by(StudentMark.course_code)
    ).scalars().all()


def save_mark(mark):
    db.session.commit()
    return mark

def get_student_approved_results(srn):
    return db.session.execute(
        db.select(StudentMark, Course)
        .join(Course, Course.code == StudentMark.course_code)
        .where(
            StudentMark.srn == srn,
            StudentMark.status == "Approved",
        )
        .order_by(Course.semester, Course.code)
    ).all()
