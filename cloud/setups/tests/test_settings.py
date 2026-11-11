"""Configuration and security settings tests."""

from datetime import timedelta

from django.conf import settings


def test_debug_is_off_by_default():
    assert settings.DEBUG is False


def test_database_is_postgresql_only():
    engine = settings.DATABASES["default"]["ENGINE"]

    assert engine == "django.db.backends.postgresql"
    assert "sqlite" not in engine


def test_tests_use_an_isolated_database_name():
    test_name = settings.DATABASES["default"]["TEST"]["NAME"]

    assert test_name == "test_devsetup"
    assert test_name.startswith("test_")


def test_jwt_configuration():
    assert (
        settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        == ("rest_framework_simplejwt.authentication.JWTAuthentication",)
    )
    assert (
        settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]
        == ("rest_framework.permissions.IsAuthenticated",)
    )

    access = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
    refresh = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]

    assert access == timedelta(minutes=15)
    assert refresh == timedelta(days=7)
    assert refresh > access
    assert settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] is True
    assert settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] is True


def test_cors_is_not_open_to_every_origin():
    assert settings.CORS_ALLOW_ALL_ORIGINS is False
    assert settings.CORS_ALLOW_CREDENTIALS is False


def test_password_hashing_is_enabled():
    assert settings.AUTH_PASSWORD_VALIDATORS
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_auth_throttling_is_configured():
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    assert "auth" in rates


def test_https_ready_switch_is_available():
    assert hasattr(settings, "SECURE_SSL_REDIRECT")
    assert hasattr(settings, "SECURE_HSTS_SECONDS")
    assert settings.SECURE_PROXY_SSL_HEADER == (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )
