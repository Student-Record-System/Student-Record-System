from app.enrollment.models import COMPLETED, CoursePrerequisite, Enrollment
from app.extensions import db


def get_enrollment(srn, course_code):
    return db.session.execute(
        db.select(Enrollment).filter_by(srn=srn, course_code=course_code)
    ).scalar_one_or_none()


def add_enrollment(enrollment):
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def completed_course_codes(srn):
    rows = db.session.execute(
        db.select(Enrollment.course_code).filter_by(srn=srn, status=COMPLETED)
    ).scalars().all()
    return set(rows)


def get_prerequisite_codes(course_code):
    rows = db.session.execute(
        db.select(CoursePrerequisite.prerequisite_code)
        .filter_by(course_code=course_code)
        .order_by(CoursePrerequisite.prerequisite_code)
    ).scalars().all()
    return list(rows)


def replace_prerequisites(course_code, prerequisite_codes):
    db.session.execute(
        db.delete(CoursePrerequisite).where(
            CoursePrerequisite.course_code == course_code
        )
    )
    for code in prerequisite_codes:
        db.session.add(
            CoursePrerequisite(course_code=course_code, prerequisite_code=code)
        )
    db.session.commit()