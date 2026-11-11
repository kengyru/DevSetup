"""Settings used only by pytest.

Environment variables are set *before* importing the production settings
module so the test suite can never accidentally point at a real database
name. pytest-django creates a dedicated test database (``test_devsetup``
by default) and destroys it after the run.
"""

import os
from pathlib import Path

import environ

# Read the local .env first so the test suite uses the same PostgreSQL
# credentials as the development server. Defaults below only fill gaps.
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / ".env")

os.environ.setdefault(
    "DJANGO_SECRET_KEY",
    "test-only-secret-key-that-is-long-and-not-used-in-production",
)
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault(
    "DJANGO_ALLOWED_HOSTS",
    "testserver,localhost,127.0.0.1",
)
os.environ.setdefault("DB_NAME", "devsetup")
os.environ.setdefault("DB_USER", "devsetup")
os.environ.setdefault("DB_PASSWORD", "devsetup")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("CORS_ALLOW_ALL_ORIGINS", "False")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "")
os.environ.setdefault("DJANGO_SECURE_SSL_REDIRECT", "False")

from .settings import *  # noqa: E402,F401,F403

DEBUG = False

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Fast hashing for tests only. Production keeps the PBKDF2 default.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Fixed, isolated test database name. Never derive it from DB_NAME so a
# misconfigured .env cannot make the tests touch real data.
DATABASES["default"]["TEST"] = {
    "NAME": os.environ.get("DB_TEST_NAME", "test_devsetup"),
}

# Tests should exercise logic, not hit rate limits. The throttle
# implementation itself is covered by a dedicated test that overrides
# the rate.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"auth": "1000/min"},
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "devsetup-tests",
    }
}
