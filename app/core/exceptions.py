"""Custom exception types and global HTTP error handlers."""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application exception."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str | None = None, error_code: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        self.error_code = error_code or self.__class__.error_code
        super().__init__(self.detail)


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication required."
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have permission to perform this action."
    error_code = "FORBIDDEN"


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid email or password."
    error_code = "INVALID_CREDENTIALS"


class MFARequiredError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Multi-factor authentication is required."
    error_code = "MFA_REQUIRED"


class InvalidMFACodeError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Invalid or expired MFA code."
    error_code = "INVALID_MFA_CODE"


class TokenExpiredError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Token has expired."
    error_code = "TOKEN_EXPIRED"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "The requested resource was not found."
    error_code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "A conflict occurred with the current state of the resource."
    error_code = "CONFLICT"


class DuplicateEmailError(ConflictError):
    detail = "An account with this email already exists."
    error_code = "DUPLICATE_EMAIL"


class SlotUnavailableError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "The requested time slot is no longer available."
    error_code = "SLOT_UNAVAILABLE"


class SlotInPastError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Cannot book a slot in the past."
    error_code = "SLOT_IN_PAST"


class DoctorNotVerifiedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Doctor profile is pending verification."
    error_code = "DOCTOR_NOT_VERIFIED"


class PaymentAlreadyProcessedError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Payment has already been processed for this idempotency key."
    error_code = "PAYMENT_ALREADY_PROCESSED"


class IdempotencyConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "A request with this idempotency key is already in progress."
    error_code = "IDEMPOTENCY_CONFLICT"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Validation failed."
    error_code = "VALIDATION_ERROR"


class RateLimitExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded. Please slow down."
    error_code = "RATE_LIMIT_EXCEEDED"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError subclasses to structured JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.detail,
            },
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions (never leaks stack traces)."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            },
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )
