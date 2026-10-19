import bcrypt
from flask_jwt_extended import create_access_token

from app.auth import repository
from app.common.errors import AuthError

GENERIC_LOGIN_ERROR = "Invalid ID or password."

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

    # STU-F-003 (account lockout) adds its check here, before the password check.

    if not verify_password(password, user.password_hash) or not user.is_active:
        raise AuthError(GENERIC_LOGIN_ERROR)

    token = create_access_token(
        identity=str(user.id),  # must be text
        additional_claims={"role": user.role},
    )
    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": {"id": user.id, "login_id": user.login_id, "role": user.role},
    }