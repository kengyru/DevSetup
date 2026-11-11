"""Cross-user authorization tests.

A user must never learn that another user's setup exists. Every foreign
resource therefore answers 404, exactly like a missing one.
"""

import pytest

from setups.models import Setup

pytestmark = pytest.mark.django_db

SETUPS_URL = "/api/setups/"


def detail_url(setup_id) -> str:
    return f"{SETUPS_URL}{setup_id}/"


@pytest.fixture
def foreign_setup(other_user):
    return Setup.objects.create(
        user=other_user,
        name="Bob's machine",
        format_version=2,
        data={"applications": [{"name": "Git", "installed": True}]},
    )


def test_list_returns_only_own_setups(auth_client, user, other_user, foreign_setup):
    own = Setup.objects.create(
        user=user,
        name="Alice's machine",
        format_version=1,
        data={"applications": []},
    )

    body = auth_client.get(SETUPS_URL).json()

    ids = {item["id"] for item in body}

    assert ids == {str(own.id)}
    assert str(foreign_setup.id) not in ids


def test_cannot_retrieve_foreign_setup(auth_client, foreign_setup):
    response = auth_client.get(detail_url(foreign_setup.id))

    assert response.status_code == 404


def test_cannot_update_foreign_setup(auth_client, foreign_setup):
    response = auth_client.put(
        detail_url(foreign_setup.id),
        {
            "name": "Hijacked",
            "data": {"applications": []},
        },
        format="json",
    )

    assert response.status_code == 404

    foreign_setup.refresh_from_db()

    assert foreign_setup.name == "Bob's machine"


def test_cannot_delete_foreign_setup(auth_client, foreign_setup):
    response = auth_client.delete(detail_url(foreign_setup.id))

    assert response.status_code == 404
    assert Setup.objects.filter(id=foreign_setup.id).exists()


def test_foreign_setup_is_not_leaked_by_creation(auth_client, other_user, foreign_setup):
    response = auth_client.post(
        SETUPS_URL,
        {
            "name": "Mine",
            "data": {"applications": []},
        },
        format="json",
    )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] != str(foreign_setup.id)
    assert Setup.objects.get(id=body["id"]).user_id != other_user.id


def test_all_setup_endpoints_require_authentication(api_client, foreign_setup):
    assert api_client.get(SETUPS_URL).status_code == 401
    assert api_client.post(SETUPS_URL, {}, format="json").status_code == 401
    assert api_client.get(detail_url(foreign_setup.id)).status_code == 401
    assert (
        api_client.put(
            detail_url(foreign_setup.id),
            {"name": "x", "data": {}},
            format="json",
        ).status_code
        == 401
    )
    assert (
        api_client.delete(detail_url(foreign_setup.id)).status_code == 401
    )
