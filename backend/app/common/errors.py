import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

from app.extensions import jwt

log = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for every error we raise on purpose."""
    status_code = 400
    code = "ERR_VALIDATION"

    def __init__(self, message, code=None, status_code=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class ValidationError(AppError):
    status_code = 400
    code = "ERR_VALIDATION"


class AuthError(AppError):
    status_code = 401
    code = "ERR_AUTH_FAILED"


class ForbiddenError(AppError):
    status_code = 403
    code = "ERR_FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "ERR_NOT_FOUND"


class ConflictError(AppError):
    """A business rule stops the action. Pass the specific code,
    for example ConflictError("Enrollment window is closed", "ERR_WINDOW_CLOSED")."""
    status_code = 409
    code = "ERR_CONFLICT"


class LockedError(AppError):
    status_code = 423
    code = "ERR_ACCOUNT_LOCKED"


def error_response(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(err):
        return error_response(err.code, err.message, err.status_code)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        codes = {404: "ERR_NOT_FOUND", 405: "ERR_METHOD_NOT_ALLOWED"}
        return error_response(codes.get(err.code, "ERR_REQUEST"), err.description, err.code)

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        log.exception("Unhandled error")  # details go to the server log only
        return error_response("ERR_INTERNAL", "Something went wrong. Please try again.", 500)

    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response("ERR_AUTH_FAILED", "Please log in to continue.", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response("ERR_AUTH_FAILED", "Your session is not valid. Please log in again.", 401)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response("ERR_TOKEN_EXPIRED", "Your session has expired. Please log in again.", 401)