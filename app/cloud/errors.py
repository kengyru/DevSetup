"""Cloud API error hierarchy."""

from __future__ import annotations


class CloudError(Exception):
    """Base exception for all cloud API errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class NetworkError(CloudError):
    """Network connectivity issues: no connection, timeout, DNS failure."""

    def __init__(self, message: str = "Нет связи с сервером") -> None:
        super().__init__(message)


class AuthError(CloudError):
    """Authentication failures: 401, invalid credentials, expired token."""

    def __init__(self, message: str = "Ошибка авторизации") -> None:
        super().__init__(message)


class ValidationError(CloudError):
    """Request validation failed (400). Contains field-level details."""

    def __init__(self, message: str = "Ошибка валидации", details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class RateLimitError(CloudError):
    """Too many requests (429)."""

    def __init__(self, message: str = "Слишком много запросов") -> None:
        super().__init__(message)


class NotFoundError(CloudError):
    """Resource not found (404)."""

    def __init__(self, message: str = "Ресурс не найден") -> None:
        super().__init__(message)


class ServerError(CloudError):
    """Server-side errors (5xx) or unexpected responses."""

    def __init__(self, message: str = "Ошибка сервера") -> None:
        super().__init__(message)