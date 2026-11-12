"""Tests for CloudClient."""

from __future__ import annotations

import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.cloud.client import CloudClient
from app.cloud.errors import (
    AuthError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class MockResponse:
    """Mock urllib response."""

    def __init__(self, data: dict | list | None, status: int = 200) -> None:
        self._data = data
        self.status = status
        self._body = json.dumps(data).encode("utf-8") if data is not None else b""

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def make_http_error(status: int, data: dict | None = None) -> urllib.error.HTTPError:
    """Create a mock HTTPError."""
    body = json.dumps(data).encode("utf-8") if data else b""
    return urllib.error.HTTPError(
        url="http://test",
        code=status,
        msg="Error",
        hdrs={},
        fp=MagicMock(read=lambda: body),
    )


class TestCloudClient:
    """Tests for CloudClient."""

    def setup_method(self) -> None:
        self.client = CloudClient(base_url="http://testserver", timeout=5)
        self.tokens_changed_calls: list[Any] = []
        self.client.on_tokens_changed = lambda t: self.tokens_changed_calls.append(t)

    # ---------------------------------------------------------------------
    # Auth tests
    # ---------------------------------------------------------------------
    @patch("urllib.request.OpenerDirector.open")
    def test_register_success(self, mock_open: MagicMock) -> None:
        mock_open.return_value = MockResponse(
            {"id": "1", "email": "test@example.com", "created_at": "2024-01-01T00:00:00Z"}, 201
        )
        result = self.client.register("test@example.com", "password123")
        assert result["email"] == "test@example.com"
        assert "password" not in str(result)

    @patch("urllib.request.OpenerDirector.open")
    def test_register_validation_error(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = make_http_error(
            400, {"email": ["A user with this email already exists."]}
        )
        with pytest.raises(ValidationError) as exc:
            self.client.register("test@example.com", "password123")
        assert "email" in str(exc.value.details)

    @patch("urllib.request.OpenerDirector.open")
    def test_login_success(self, mock_open: MagicMock) -> None:
        mock_open.return_value = MockResponse(
            {"access": "access-token", "refresh": "refresh-token"}
        )
        result = self.client.login("test@example.com", "password123")
        assert result["access"] == "access-token"
        assert result["refresh"] == "refresh-token"
        assert self.client._access_token == "access-token"
        assert self.client._refresh_token == "refresh-token"
        assert self.tokens_changed_calls == ["refresh-token"]

    @patch("urllib.request.OpenerDirector.open")
    def test_login_auth_error(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = make_http_error(401, {"detail": "No active account found"})
        with pytest.raises(AuthError) as exc:
            self.client.login("test@example.com", "wrong")
        assert "Неверные учётные данные" in str(exc.value)
        assert "wrong" not in str(exc.value)
        assert "password123" not in str(exc.value)

    @patch("urllib.request.OpenerDirector.open")
    def test_logout_clears_tokens(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        self.client.logout()
        assert self.client._access_token is None
        assert self.client._refresh_token is None
        assert self.tokens_changed_calls == [None]

    @patch("urllib.request.OpenerDirector.open")
    def test_restore_session_success(self, mock_open: MagicMock) -> None:
        mock_open.return_value = MockResponse(
            {"access": "new-access", "refresh": "new-refresh"}
        )
        result = self.client.restore_session("old-refresh")
        assert result["access"] == "new-access"
        assert result["refresh"] == "new-refresh"
        assert self.client._access_token == "new-access"
        assert self.client._refresh_token == "new-refresh"
        assert self.tokens_changed_calls == ["new-refresh"]

    @patch("urllib.request.OpenerDirector.open")
    def test_restore_session_auth_error(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = make_http_error(401, {"detail": "Token is invalid"})
        with pytest.raises(AuthError):
            self.client.restore_session("bad-refresh")

    # ---------------------------------------------------------------------
    # Setups CRUD tests
    # ---------------------------------------------------------------------
    @patch("urllib.request.OpenerDirector.open")
    def test_list_setups_success(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.return_value = MockResponse(
            [{"id": "1", "name": "Setup 1", "format_version": 2, "created_at": "..."}]
        )
        result = self.client.list_setups()
        assert len(result) == 1
        assert result[0]["name"] == "Setup 1"

    @patch("urllib.request.OpenerDirector.open")
    def test_get_setup_success(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.return_value = MockResponse(
            {"id": "1", "name": "Setup 1", "format_version": 2, "data": {}, "created_at": "..."}
        )
        result = self.client.get_setup("1")
        assert result["name"] == "Setup 1"

    @patch("urllib.request.OpenerDirector.open")
    def test_create_setup_success(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.return_value = MockResponse(
            {"id": "1", "name": "New", "format_version": 2, "data": {}, "created_at": "..."}, 201
        )
        result = self.client.create_setup("New", {"version": 2, "apps": []})
        assert result["name"] == "New"

    @patch("urllib.request.OpenerDirector.open")
    def test_update_setup_success(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.return_value = MockResponse(
            {"id": "1", "name": "Updated", "format_version": 2, "data": {}, "created_at": "..."}
        )
        result = self.client.update_setup("1", "Updated", {"version": 2, "apps": []})
        assert result["name"] == "Updated"

    @patch("urllib.request.OpenerDirector.open")
    def test_delete_setup_success(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.return_value = MockResponse(None, 204)
        self.client.delete_setup("1")

    # ---------------------------------------------------------------------
    # Error handling tests
    # ---------------------------------------------------------------------
    @patch("urllib.request.OpenerDirector.open")
    def test_validation_error_400(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.side_effect = make_http_error(400, {"name": ["This field may not be blank."]})
        with pytest.raises(ValidationError) as exc:
            self.client.create_setup("", {})
        assert "name" in str(exc.value.details)

    @patch("urllib.request.OpenerDirector.open")
    def test_auth_error_401_on_setups(self, mock_open: MagicMock) -> None:
        self.client._access_token = "expired"
        self.client._refresh_token = "refresh"
        mock_open.side_effect = [
            make_http_error(401, {"detail": "Token expired"}),
            MockResponse({"access": "new-access", "refresh": "new-refresh"}),
            MockResponse([{"id": "1", "name": "Setup"}]),
        ]
        result = self.client.list_setups()
        assert len(result) == 1
        assert self.client._access_token == "new-access"
        assert self.client._refresh_token == "new-refresh"
        assert self.tokens_changed_calls[-1] == "new-refresh"

    @patch("urllib.request.OpenerDirector.open")
    def test_auth_error_401_refresh_fails(self, mock_open: MagicMock) -> None:
        self.client._access_token = "expired"
        self.client._refresh_token = "bad-refresh"
        mock_open.side_effect = [
            make_http_error(401, {"detail": "Token expired"}),
            make_http_error(401, {"detail": "Token is invalid"}),
        ]
        with pytest.raises(AuthError):
            self.client.list_setups()
        assert self.client._access_token is None
        assert self.client._refresh_token is None

    @patch("urllib.request.OpenerDirector.open")
    def test_not_found_404(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.side_effect = make_http_error(404, {"detail": "Not found."})
        with pytest.raises(NotFoundError):
            self.client.get_setup("nonexistent")

    @patch("urllib.request.OpenerDirector.open")
    def test_rate_limit_429(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.side_effect = make_http_error(429, {"detail": "Throttled"})
        with pytest.raises(RateLimitError):
            self.client.list_setups()

    @patch("urllib.request.OpenerDirector.open")
    def test_server_error_500(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.side_effect = make_http_error(500, {"detail": "A server error occurred."})
        with pytest.raises(ServerError):
            self.client.list_setups()

    @patch("urllib.request.OpenerDirector.open")
    def test_network_error_timeout(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = TimeoutError()
        with pytest.raises(NetworkError) as exc:
            self.client.register("test@example.com", "password123")
        assert "время ожидания" in str(exc.value).lower()

    @patch("urllib.request.OpenerDirector.open")
    def test_network_error_connection_refused(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = urllib.error.URLError(ConnectionRefusedError())
        with pytest.raises(NetworkError) as exc:
            self.client.register("test@example.com", "password123")
        assert "соединения" in str(exc.value).lower()

    # ---------------------------------------------------------------------
    # Token handling tests
    # ---------------------------------------------------------------------
    @patch("urllib.request.OpenerDirector.open")
    def test_on_tokens_changed_called_on_login(self, mock_open: MagicMock) -> None:
        mock_open.return_value = MockResponse({"access": "a", "refresh": "r"})
        self.client.login("test@example.com", "password")
        assert self.tokens_changed_calls == ["r"]

    @patch("urllib.request.OpenerDirector.open")
    def test_on_tokens_changed_called_on_refresh(self, mock_open: MagicMock) -> None:
        self.client._access_token = "old"
        self.client._refresh_token = "old-r"
        mock_open.side_effect = [
            make_http_error(401, {"detail": "expired"}),
            MockResponse({"access": "new", "refresh": "new-r"}),
            MockResponse([]),
        ]
        self.client.list_setups()
        assert "new-r" in self.tokens_changed_calls

    @patch("urllib.request.OpenerDirector.open")
    def test_on_tokens_changed_called_on_logout(self, mock_open: MagicMock) -> None:
        self.client._access_token = "a"
        self.client._refresh_token = "r"
        self.client.logout()
        assert self.tokens_changed_calls == [None]

    @patch("urllib.request.OpenerDirector.open")
    def test_on_tokens_changed_called_on_restore_session(self, mock_open: MagicMock) -> None:
        mock_open.return_value = MockResponse({"access": "a", "refresh": "r"})
        self.client.restore_session("saved-r")
        assert self.tokens_changed_calls == ["r"]

    # ---------------------------------------------------------------------
    # Security: secrets not in error messages
    # ---------------------------------------------------------------------
    @patch("urllib.request.OpenerDirector.open")
    def test_password_not_in_error_message(self, mock_open: MagicMock) -> None:
        mock_open.side_effect = make_http_error(401, {"detail": "Invalid"})
        with pytest.raises(AuthError) as exc:
            self.client.login("test@example.com", "secret-password-123")
        error_str = str(exc.value)
        assert "secret-password-123" not in error_str
        assert "password" not in error_str.lower()

    @patch("urllib.request.OpenerDirector.open")
    def test_tokens_not_in_error_message(self, mock_open: MagicMock) -> None:
        self.client._access_token = "secret-access-token"
        self.client._refresh_token = "secret-refresh-token"
        mock_open.side_effect = make_http_error(500, {"detail": "Server error"})
        with pytest.raises(ServerError) as exc:
            self.client.list_setups()
        error_str = str(exc.value)
        assert "secret-access-token" not in error_str
        assert "secret-refresh-token" not in error_str

    # ---------------------------------------------------------------------
    # Proxy bypass test
    # ---------------------------------------------------------------------
    def test_opener_bypasses_proxy(self) -> None:
        """Verify opener is built with empty ProxyHandler (no system proxy)."""
        client = CloudClient()
        # When ProxyHandler({}) is passed to build_opener, it replaces the default
        # system proxy handler with one that has no proxies configured.
        # The handler list won't contain ProxyHandler because empty ProxyHandler
        # is optimized out, but the effect is that no proxy is used.
        handlers = client._opener.handlers
        proxy_handlers = [h for h in handlers if isinstance(h, urllib.request.ProxyHandler)]
        # Empty ProxyHandler is not in the list - that's the expected behavior
        # for proxy bypass. Just verify no system proxy handler is present.
        assert len(proxy_handlers) == 0

    # ---------------------------------------------------------------------
    # Malformed response handling
    # ---------------------------------------------------------------------
    @patch("urllib.request.OpenerDirector.open")
    def test_non_json_response_raises_server_error(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b"Not JSON"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = lambda s, *a: None
        mock_open.return_value = mock_response

        with pytest.raises(ServerError) as exc:
            self.client.list_setups()
        assert "Некорректный ответ сервера" in str(exc.value)

    @patch("urllib.request.OpenerDirector.open")
    def test_unexpected_status_raises_server_error(self, mock_open: MagicMock) -> None:
        self.client._access_token = "access"
        self.client._refresh_token = "refresh"
        mock_open.side_effect = make_http_error(302, {"detail": "Redirect"})
        with pytest.raises(ServerError) as exc:
            self.client.list_setups()
        assert "Неожиданный статус 302" in str(exc.value)