"""Application error taxonomy. Owner: M3 (C-01).

Handlers in `app.main` turn these into the canonical `ErrorResponse` body, so a
domain module raises an `AppError` instead of building an HTTP response. Codes
are part of the public contract; keep them stable.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class. `status` and `code` are what reaches the client."""

    status = 500
    code = "INTERNAL_ERROR"
    retryable = False
    message = "The request could not be completed."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message


class InvalidRequest(AppError):
    status = 422
    code = "INVALID_REQUEST"
    message = "The request does not match the API contract."


class NotFound(AppError):
    status = 404
    code = "NOT_FOUND"
    message = "The requested resource does not exist."


class Forbidden(AppError):
    status = 403
    code = "FORBIDDEN"
    message = "This session may not access that resource."


class PayloadTooLarge(AppError):
    status = 413
    code = "PAYLOAD_TOO_LARGE"
    message = "The uploaded file exceeds the configured limit."


class ConflictError(AppError):
    status = 409
    code = "CONFLICT"
    message = "The resource changed while this request was in flight."


class DependencyUnavailable(AppError):
    """A configured external service failed. Never presented as a usable result."""

    status = 503
    code = "DEPENDENCY_UNAVAILABLE"
    retryable = True
    message = "A required service is unavailable. The request can be retried."


class NotImplementedFeature(AppError):
    status = 501
    code = "NOT_IMPLEMENTED"
    message = "This feature is planned but not implemented."
