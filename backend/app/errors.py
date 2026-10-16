"""API errors that the exception handlers turn into contract ErrorResponse bodies."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, error_code: str, message: str, retry_after_s: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.message = message
        self.retry_after_s = retry_after_s


def validation(message: str) -> ApiError:
    return ApiError(400, "VALIDATION", message)


def too_many_images(limit: int) -> ApiError:
    return ApiError(400, "TOO_MANY_IMAGES", f"Send at most {limit} photos per scan.")


def image_too_large(limit_mb: float) -> ApiError:
    return ApiError(413, "BAD_IMAGE", f"Each photo must be smaller than {limit_mb:g} MB.")


def bad_image(message: str) -> ApiError:
    return ApiError(422, "BAD_IMAGE", message)
