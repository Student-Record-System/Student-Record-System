from app.extensions import db
from app.grades.models import StudentMark


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
