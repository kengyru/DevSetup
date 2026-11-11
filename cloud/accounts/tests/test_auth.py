import logging

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

User = get_user_model()

VALID_PASSWORD = "ValidPass!2345"

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
SETUPS_URL = "/api/setups/"


def test_register_success(db, api_client):
    response = api_client.post(
        REGISTER_URL,
        {
            "email": "New.User@Example.com",
            "password": VALID_PASSWORD,
        },
        format="json",
    )

    assert response.status_code == 201

    body = response.json()

    assert set(body) == {"id", "email", "created_at"}
    assert body["email"] == "new.user@example.com"
    assert body["created_at"]

    user = User.objects.get(email="new.user@example.com")
    assert user.password != VALID_PASSWORD
    assert user.check_password(VALID_PASSWORD)


def test_duplicate_email_is_rejected_case_insensitively(
    db,
    api_client,
):
    User.objects.create_user(
        email="alice@example.com",
        password=VALID_PASSWORD,
    )

    response = api_client.post(
        REGISTER_URL,
        {
            "email": "ALICE@example.com",
            "password": VALID_PASSWORD,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "email" in response.json()


def test_duplicate_email_from_api_is_rejected(db, api_client):
    payload = {
        "email": "dup@example.com",
        "password": VALID_PASSWORD,
    }

    assert api_client.post(
        REGISTER_URL,
        payload,
        format="json",
    ).status_code == 201

    second = api_client.post(
        REGISTER_URL,
        payload,
        format="json",
    )

    assert second.status_code == 400
    assert "email" in second.json()


def test_invalid_email_is_rejected(db, api_client):
    response = api_client.post(
        REGISTER_URL,
        {
            "email": "not-an-email",
            "password": VALID_PASSWORD,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "email" in response.json()


def test_weak_password_is_rejected(db, api_client):
    response = api_client.post(
        REGISTER_URL,
        {
            "email": "weak@example.com",
            "password": "12345678",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "password" in response.json()


def test_login_success_returns_tokens(user, api_client):
    response = api_client.post(
        LOGIN_URL,
        {
            "email": user.email,
            "password": VALID_PASSWORD,
        },
        format="json",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access"]
    assert body["refresh"]
    assert "password" not in body

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {body['access']}"
    )

    assert client.get(SETUPS_URL).status_code == 200


def test_login_is_case_insensitive(user, api_client):
    response = api_client.post(
        LOGIN_URL,
        {
            "email": "ALICE@Example.com",
            "password": VALID_PASSWORD,
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["access"]


def test_login_with_wrong_password_returns_401(user, api_client):
    response = api_client.post(
        LOGIN_URL,
        {
            "email": user.email,
            "password": "WrongPass!2345",
        },
        format="json",
    )

    assert response.status_code == 401
    assert "access" not in response.json()


def test_refresh_success_rotates_and_blacklists_old_token(
    user,
    api_client,
):
    login = api_client.post(
        LOGIN_URL,
        {
            "email": user.email,
            "password": VALID_PASSWORD,
        },
        format="json",
    ).json()

    refresh = login["refresh"]

    response = api_client.post(
        REFRESH_URL,
        {"refresh": refresh},
        format="json",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access"]
    assert body["refresh"]
    assert body["refresh"] != refresh

    reuse = api_client.post(
        REFRESH_URL,
        {"refresh": refresh},
        format="json",
    )

    assert reuse.status_code == 401


def test_invalid_refresh_token_is_rejected(api_client):
    response = api_client.post(
        REFRESH_URL,
        {"refresh": "not-a-token"},
        format="json",
    )

    assert response.status_code == 401


def test_unauthorized_requests_are_rejected(api_client):
    assert api_client.get(SETUPS_URL).status_code == 401

    assert (
        api_client.post(
            SETUPS_URL,
            {
                "name": "x",
                "data": {"applications": []},
            },
            format="json",
        ).status_code
        == 401
    )


def test_invalid_bearer_token_is_rejected(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid")

    assert api_client.get(SETUPS_URL).status_code == 401


def test_register_response_never_contains_password_hash(db, api_client):
    response = api_client.post(
        REGISTER_URL,
        {
            "email": "hash@example.com",
            "password": VALID_PASSWORD,
        },
        format="json",
    )

    raw = response.content.decode("utf-8").lower()

    assert "password" not in raw
    assert "pbkdf2" not in raw
    assert "md5" not in raw


def test_tokens_and_passwords_are_not_logged(
    user,
    api_client,
    caplog,
):
    caplog.set_level(logging.INFO)

    login = api_client.post(
        LOGIN_URL,
        {
            "email": user.email,
            "password": VALID_PASSWORD,
        },
        format="json",
    ).json()

    refresh = login["refresh"]
    access = login["access"]

    api_client.post(
        REFRESH_URL,
        {"refresh": refresh},
        format="json",
    )

    logged = caplog.text

    assert VALID_PASSWORD not in logged
    assert access not in logged
    assert refresh not in logged


def test_login_and_refresh_endpoints_are_throttled(
    user,
    api_client,
    monkeypatch,
):
    # SimpleRateThrottle keeps a class level copy of the rates, so the
    # normal settings override would not be picked up here.
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"auth": "2/min"},
    )
    cache.clear()

    statuses = []

    for _ in range(3):
        statuses.append(
            api_client.post(
                LOGIN_URL,
                {
                    "email": user.email,
                    "password": "WrongPass!2345",
                },
                format="json",
            ).status_code
        )

    assert statuses[0] == 401
    assert statuses[1] == 401
    assert statuses[2] == 429


def test_register_requires_email_and_password(db, api_client):
    response = api_client.post(REGISTER_URL, {}, format="json")

    assert response.status_code == 400
    assert "email" in response.json()
    assert "password" in response.json()


if __name__ == "__main__":
    pytest.main([__file__])
