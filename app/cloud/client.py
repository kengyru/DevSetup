"""HTTP client for DevSetup Cloud API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from .errors import (
    AuthError,
    CloudError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class CloudClient:
    """Client for DevSetup Cloud API.

    Handles authentication, token refresh, and CRUD operations for setups.
    All requests bypass system proxy. Access token is kept in memory only.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: int = 10,
        on_tokens_changed: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.on_tokens_changed = on_tokens_changed

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None

        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _set_tokens(self, access: Optional[str], refresh: Optional[str]) -> None:
        self._access_token = access
        self._refresh_token = refresh
        if self.on_tokens_changed is not None:
            self.on_tokens_changed(refresh)

    # ---------------------------------------------------------------------
    # Public API: Auth
    # ---------------------------------------------------------------------
    def register(self, email: str, password: str) -> dict[str, Any]:
        """Register a new user account."""
        return self._request(
            "POST",
            "/api/auth/register/",
            {"email": email, "password": password},
            auth_required=False,
        )

    def login(self, email: str, password: str) -> dict[str, str]:
        """Log in and obtain access/refresh tokens."""
        data = self._request(
            "POST",
            "/api/auth/login/",
            {"email": email, "password": password},
            auth_required=False,
        )
        self._set_tokens(data["access"], data["refresh"])
        return {"access": data["access"], "refresh": data["refresh"]}

    def logout(self) -> None:
        """Clear stored tokens and notify listener."""
        self._set_tokens(None, None)

    def restore_session(self, refresh_token: str) -> dict[str, str]:
        """Obtain new access token using a saved refresh token."""
        data = self._request(
            "POST",
            "/api/auth/refresh/",
            {"refresh": refresh_token},
            auth_required=False,
        )
        self._set_tokens(data["access"], data["refresh"])
        return {"access": data["access"], "refresh": data["refresh"]}

    # ---------------------------------------------------------------------
    # Public API: Setups CRUD
    # ---------------------------------------------------------------------
    def list_setups(self) -> list[dict[str, Any]]:
        """List all setups for the authenticated user."""
        return self._request_with_refresh("GET", "/api/setups/")

    def get_setup(self, setup_id: str) -> dict[str, Any]:
        """Retrieve a single setup by ID."""
        return self._request_with_refresh("GET", f"/api/setups/{setup_id}/")

    def create_setup(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new setup."""
        return self._request_with_refresh("POST", "/api/setups/", {"name": name, "data": data})

    def update_setup(self, setup_id: str, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Fully update an existing setup (PUT)."""
        return self._request_with_refresh("PUT", f"/api/setups/{setup_id}/", {"name": name, "data": data})

    def delete_setup(self, setup_id: str) -> None:
        """Delete a setup."""
        self._request_with_refresh("DELETE", f"/api/setups/{setup_id}/", expected_status=204)

    # ---------------------------------------------------------------------
    # Internal HTTP
    # ---------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
        auth_required: bool = True,
        expected_status: int = 200,
    ) -> Any:
        """Perform HTTP request without token refresh logic."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}

        if auth_required:
            if not self._access_token:
                raise AuthError("Требуется авторизация")
            headers["Authorization"] = f"Bearer {self._access_token}"

        data = json.dumps(body).encode("utf-8") if body is not None else None

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            response = self._opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            self._handle_http_error(e)
        except urllib.error.URLError as e:
            raise NetworkError(f"Ошибка соединения: {e.reason}") from e
        except TimeoutError as e:
            raise NetworkError("Превышено время ожидания") from e
        except Exception as e:
            raise NetworkError(f"Сетевая ошибка: {e}") from e

        status = response.getcode()
        if status != expected_status and not (200 <= status < 300):
            try:
                error_body = response.read().decode("utf-8")
                error_data = json.loads(error_body) if error_body else {}
            except Exception:
                error_data = {}
            self._raise_for_status(status, error_data)

        response_body = response.read().decode("utf-8")
        if not response_body:
            return None

        try:
            return json.loads(response_body)
        except json.JSONDecodeError as e:
            raise ServerError(f"Некорректный ответ сервера: {e}") from e

    def _request_with_refresh(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
        auth_required: bool = True,
        expected_status: int = 200,
    ) -> Any:
        """Wrapper that retries once on 401 using token refresh."""
        try:
            return self._request(method, path, body, auth_required, expected_status)
        except AuthError as e:
            if not auth_required or not self._refresh_token:
                raise
            try:
                self._refresh_access_token()
            except AuthError:
                self._set_tokens(None, None)
                raise
            return self._request(method, path, body, auth_required, expected_status)

    def _refresh_access_token(self) -> None:
        """Use refresh token to obtain new access token (rotation)."""
        if not self._refresh_token:
            raise AuthError("Нет refresh-токена")

        data = self._request(
            "POST",
            "/api/auth/refresh/",
            {"refresh": self._refresh_token},
            auth_required=False,
        )
        self._set_tokens(data["access"], data["refresh"])

    def _handle_http_error(self, error: urllib.error.HTTPError) -> None:
        """Parse HTTP error response and raise appropriate exception."""
        status = error.code
        try:
            error_body = error.read().decode("utf-8")
            error_data = json.loads(error_body) if error_body else {}
        except Exception:
            error_data = {}

        self._raise_for_status(status, error_data)

    def _raise_for_status(self, status: int, data: dict[str, Any]) -> None:
        """Map HTTP status to exception."""
        if status == 400:
            detail = data.get("detail", "Ошибка валидации")
            raise ValidationError(detail, data)
        if status == 401:
            raise AuthError("Неверные учётные данные")
        if status == 404:
            raise NotFoundError("Ресурс не найден")
        if status == 429:
            raise RateLimitError("Слишком много запросов")
        if 500 <= status < 600:
            raise ServerError("Ошибка сервера")
        raise ServerError(f"Неожиданный статус {status}")