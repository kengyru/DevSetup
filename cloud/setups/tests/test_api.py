"""Setup CRUD API tests."""

import uuid

import pytest

from setups.models import Setup

pytestmark = pytest.mark.django_db

SETUPS_URL = "/api/setups/"


def detail_url(setup_id) -> str:
    return f"{SETUPS_URL}{setup_id}/"


def v2_payload(name: str = "Workstation") -> dict:
    return {
        "name": name,
        "data": {
            "format_version": 2,
            "applications": [
                {
                    "name": "Git",
                    "version": "2.45.0",
                    "path": "C:\\Program Files\\Git",
                    "installed": True,
                    "package_id": "Git.Git",
                },
                {
                    "name": "Visual Studio Code",
                    "version": "1.90.0",
                    "installed": True,
                    "package_id": "Microsoft.VisualStudioCode",
                    "extensions": ["ms-python.python"],
                },
            ],
            "git_config": {
                "user.name": "Alice",
                "user.email": "alice@example.com",
            },
            "python_packages": ["Django==5.2.4", "requests==2.32.3"],
            "npm_packages": ["typescript"],
            "wsl_distributions": [{"name": "Ubuntu", "version": 2}],
            "environment_variables": {"NODE_ENV": "development"},
            "secret_environment_variables": ["NPM_TOKEN"],
            "terminal": {
                "available": True,
                "profiles": ["Windows.Terminal.PowershellCore"],
            },
        },
    }


def test_create_setup(auth_client, user):
    response = auth_client.post(
        SETUPS_URL,
        v2_payload(),
        format="json",
    )

    assert response.status_code == 201

    body = response.json()

    assert uuid.UUID(body["id"])
    assert body["name"] == "Workstation"
    assert body["format_version"] == 2
    assert body["created_at"]
    assert body["updated_at"]
    assert body["data"]["applications"]
    assert body["data"]["git_config"]["user.name"] == "Alice"

    setup = Setup.objects.get(id=body["id"])

    assert setup.user_id == user.id
    assert setup.format_version == 2


def test_create_setup_trims_name(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        v2_payload("  Padded name  "),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Padded name"


def test_create_v1_setup_without_format_version(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        {
            "name": "Legacy",
            "data": {
                "applications": [
                    {
                        "name": "7-Zip",
                        "version": "24.07",
                        "installed": True,
                    }
                ]
            },
        },
        format="json",
    )

    assert response.status_code == 201

    body = response.json()

    assert body["format_version"] == 1
    assert set(body["data"]) == {"applications"}
    assert body["data"]["applications"][0]["name"] == "7-Zip"


def test_client_cannot_override_format_version(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        {
            "name": "Spoofed",
            "format_version": 2,
            "data": {"applications": []},
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["format_version"] == 1


def test_client_cannot_assign_another_owner(auth_client, user, other_user):
    response = auth_client.post(
        SETUPS_URL,
        {
            **v2_payload("Owned by caller"),
            "user": other_user.id,
        },
        format="json",
    )

    assert response.status_code == 201

    setup = Setup.objects.get(id=response.json()["id"])

    assert setup.user_id == user.id


def test_list_returns_metadata_only(auth_client, user):
    Setup.objects.create(
        user=user,
        name="First",
        format_version=2,
        data={"applications": []},
    )
    Setup.objects.create(
        user=user,
        name="Second",
        format_version=1,
        data={"applications": []},
    )

    response = auth_client.get(SETUPS_URL)

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body, list)
    assert len(body) == 2

    for item in body:
        assert set(item) == {
            "id",
            "name",
            "format_version",
            "created_at",
            "updated_at",
        }
        assert "data" not in item


def test_list_is_ordered_newest_first(auth_client, user):
    first = Setup.objects.create(
        user=user,
        name="Older",
        format_version=1,
        data={"applications": []},
    )
    second = Setup.objects.create(
        user=user,
        name="Newer",
        format_version=1,
        data={"applications": []},
    )

    body = auth_client.get(SETUPS_URL).json()

    assert [item["id"] for item in body] == [
        str(second.id),
        str(first.id),
    ]


def test_retrieve_setup_includes_data(auth_client, user):
    setup = Setup.objects.create(
        user=user,
        name="Stored",
        format_version=2,
        data={"applications": []},
    )

    response = auth_client.get(detail_url(setup.id))

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(setup.id)
    assert body["name"] == "Stored"
    assert body["format_version"] == 2
    assert body["data"] == {"applications": []}


def test_update_setup_with_put(auth_client, user):
    setup = Setup.objects.create(
        user=user,
        name="Old name",
        format_version=1,
        data={"applications": []},
    )

    response = auth_client.put(
        detail_url(setup.id),
        v2_payload("New name"),
        format="json",
    )

    assert response.status_code == 200

    setup.refresh_from_db()

    assert setup.name == "New name"
    assert setup.format_version == 2
    assert setup.data["git_config"]["user.name"] == "Alice"

    body = response.json()

    assert body["name"] == "New name"
    assert body["format_version"] == 2


def test_update_can_downgrade_to_v1(auth_client, user):
    setup = Setup.objects.create(
        user=user,
        name="Full",
        format_version=2,
        data={"applications": [], "git_config": {"user.name": "A"}},
    )

    response = auth_client.put(
        detail_url(setup.id),
        {
            "name": "V1 again",
            "data": {"format_version": 1, "applications": []},
        },
        format="json",
    )

    assert response.status_code == 200

    setup.refresh_from_db()

    assert setup.format_version == 1
    assert setup.data == {"applications": []}


def test_patch_is_not_allowed(auth_client, user):
    setup = Setup.objects.create(
        user=user,
        name="No patch",
        format_version=1,
        data={"applications": []},
    )

    response = auth_client.patch(
        detail_url(setup.id),
        {"name": "Renamed"},
        format="json",
    )

    assert response.status_code == 405

    setup.refresh_from_db()
    assert setup.name == "No patch"


def test_delete_setup(auth_client, user):
    setup = Setup.objects.create(
        user=user,
        name="Delete me",
        format_version=1,
        data={"applications": []},
    )

    response = auth_client.delete(detail_url(setup.id))

    assert response.status_code == 204
    assert not Setup.objects.filter(id=setup.id).exists()


def test_invalid_json_body_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        data="{not-json",
        content_type="application/json",
    )

    assert response.status_code == 400


def test_blank_name_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        {"name": "   ", "data": {"applications": []}},
        format="json",
    )

    assert response.status_code == 400
    assert "name" in response.json()


def test_name_longer_than_100_characters_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        {"name": "a" * 101, "data": {"applications": []}},
        format="json",
    )

    assert response.status_code == 400
    assert "name" in response.json()


def test_missing_name_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        {"data": {"applications": []}},
        format="json",
    )

    assert response.status_code == 400
    assert "name" in response.json()


def test_missing_data_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        {"name": "No data"},
        format="json",
    )

    assert response.status_code == 400
    assert "data" in response.json()


def test_unknown_setup_id_returns_404(auth_client):
    response = auth_client.get(detail_url(uuid.uuid4()))

    assert response.status_code == 404


def test_malformed_setup_id_returns_404(auth_client):
    response = auth_client.get(f"{SETUPS_URL}not-a-uuid/")

    assert response.status_code == 404
