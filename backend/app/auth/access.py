from functools import wraps

from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.auth import repository
from app.common.errors import AuthError, ForbiddenError


def current_user():
    return repository.get_user_by_id(int(get_jwt_identity()))


def _require_active_user():
    """Check the token, then re-read the account so a deactivated user is refused at once."""
    verify_jwt_in_request()
    user = current_user()
    if user is None or not user.is_active:
        raise AuthError("Your account is not active.")
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _require_active_user()
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _require_active_user()
            if get_jwt().get("role") not in roles:  # role comes from the token
                raise ForbiddenError("You do not have permission to do this.")
            return fn(*args, **kwargs)
        return wrapper
    return decorator