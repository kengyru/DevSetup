"""Shared pytest fixtures for the cloud backend."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

User = get_user_model()

VALID_PASSWORD = "ValidPass!2345"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Keep the auth throttle counter from leaking between tests."""

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="alice@example.com",
        password=VALID_PASSWORD,
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="bob@example.com",
        password=VALID_PASSWORD,
    )


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_auth_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client
