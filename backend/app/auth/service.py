from datetime import timedelta
import re
import secrets
import string

import bcrypt
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError

from app.auth import repository
from app.auth.models import User
from app.common.audit import record_event
from app.common.clock import Clock
from app.common.errors import (
    AuthError,
    ConflictError,
    LockedError,
    ValidationError,
)
from app.common.notifications import get_notification_client
from app.common.roles import ALL_ROLES
from app.extensions import db

GENERIC_LOGIN_ERROR = "Invalid ID or password."
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Used when the ID does not exist, so the response takes about as long as a real check.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt())


def hash_password(plain):
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def login(login_id, password):
    user = repository.get_user_by_login_id(login_id)

    if user is None:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
        raise AuthError(GENERIC_LOGIN_ERROR)

    # Do not count attempts against inactive accounts.
    if not user.is_active:
        verify_password(password, user.password_hash)
        raise AuthError(GENERIC_LOGIN_ERROR)

    now = Clock.now()

    # Reject login attempts while the account is locked.
    if user.locked_until is not None:
        if user.locked_until > now:
            raise LockedError(
                "Your account is temporarily locked. Please try again later."
            )

        # The lockout period has expired; begin a fresh sequence.
        user.locked_until = None
        user.failed_attempts = 0

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    # Incorrect passwords increment the consecutive-failure counter.
    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1

        if user.failed_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)

            record_event(
                "ACCOUNT_LOCKED",
                user_id=user.id,
                login_id=user.login_id,
                details={
                    "failed_attempts": user.failed_attempts,
                    "lockout_minutes": 15,
                },
            )

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

            raise LockedError(
                "Your account has been locked for 15 minutes "
                "after 5 consecutive failed login attempts."
            )

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        raise AuthError(GENERIC_LOGIN_ERROR)

    # Successful login resets consecutive failures and any expired lock.
    if user.failed_attempts != 0 or user.locked_until is not None:
        user.failed_attempts = 0
        user.locked_until = None

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    token = create_access_token(
        identity=str(user.id),  # must be text
        additional_claims={"role": user.role},
    )
    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": {"id": user.id, "login_id": user.login_id, "role": user.role},
    }


def generate_temporary_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_user(login_id, email, role):
    if role not in ALL_ROLES:
        raise ValidationError("role must be one of: " + ", ".join(ALL_ROLES))
    if not EMAIL_PATTERN.match(email):
        raise ValidationError("A valid email address is required.")
    if repository.get_user_by_login_id(login_id) is not None:
        raise ConflictError("A user with this ID already exists.", "ERR_USER_EXISTS")

    password = generate_temporary_password()
    user = User(
        login_id=login_id, email=email,
        password_hash=hash_password(password), role=role,
    )
    try:
        repository.add_user(user)
    except IntegrityError:  # two requests with the same ID at the same moment
        db.session.rollback()
        raise ConflictError("A user with this ID already exists.", "ERR_USER_EXISTS")

    # TODO: Account creation auditing is outside the scope of STU-F-003.
    body = (
        "Your Student Record System account has been created.\n"
        f"Login ID: {login_id}\n"
        f"Temporary password: {password}\n"
        "Please log in and keep these details private."
    )
    get_notification_client().send(
        email, "Your Student Record System account", body, "ACCOUNT_CREATED"
    )
    return user