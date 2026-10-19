from app.auth.models import User
from app.extensions import db


def get_user_by_login_id(login_id):
    return db.session.execute(
        db.select(User).filter_by(login_id=login_id)
    ).scalar_one_or_none()


def get_user_by_id(user_id):
    return db.session.get(User, user_id)


def add_user(user):
    db.session.add(user)
    db.session.commit()
    return user