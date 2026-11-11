"""Unit tests for the independent server-side setup schema."""

import pytest

from setups.schema import (
    MAX_SETUP_BYTES,
    SanitizedSetup,
    SetupValidationError,
    validate_setup_payload,
)


def validate_error(payload) -> dict:
    with pytest.raises(SetupValidationError) as error:
        validate_setup_payload(payload)

    return error.value.detail


def test_missing_format_version_means_v1():
    result = validate_setup_payload(
        {
            "applications": [
                {"name": "Git", "installed": True},
            ],
            "git_config": {"user.name": "Alice"},
        }
    )

    assert isinstance(result, SanitizedSetup)
    assert result.format_version == 1
    assert set(result.data) == {"applications"}
    assert result.data["applications"][0]["name"] == "Git"


def test_v1_ignores_v2_only_fields():
    result = validate_setup_payload(
        {
            "format_version": 1,
            "applications": [],
            "python_packages": ["Django==5.2.4"],
            "npm_packages": ["typescript"],
        }
    )

    assert result.format_version == 1
    assert result.data == {"applications": []}


def test_git_config_allowlist_and_normalisation():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "git_config": {
                "user.name": "Alice",
                "USER.EMAIL": "alice@example.com",
                "core.editor": "code --wait",
                "credential.helper": "store",
                "alias.ci": "!sh -c 'rm -rf /'",
                "url.https://token@example.com/.insteadof": "https://",
                "gpg.program": "gpg",
            },
        }
    )

    assert result.data["git_config"] == {
        "core.editor": "code --wait",
        "user.email": "alice@example.com",
        "user.name": "Alice",
    }


def test_git_config_drops_unsafe_values():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "git_config": {
                "user.name": "line1\nline2",
                "user.email": 42,
                "core.editor": "x" * 2_001,
                "pull.rebase": "true",
            },
        }
    )

    assert result.data["git_config"] == {"pull.rebase": "true"}


def test_python_package_filtering():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "python_packages": [
                "Django==5.2.4",
                "django==5.2.4",
                "requests==2.32.3",
                "pip==24.0",
                "setuptools==70.0.0",
                "-e .",
                "--index-url https://evil.example/simple",
                "https://evil.example/pkg.whl",
                "Django>=5",
                "git+https://evil.example/repo.git",
                "package==1.0; rm -rf /",
                "package == 1.0",
                "CamelCase==1.0",
            ],
        }
    )

    assert result.data["python_packages"] == [
        "Django==5.2.4",
        "requests==2.32.3",
        "CamelCase==1.0",
    ]


def test_npm_package_filtering():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "npm_packages": [
                "typescript",
                "@types/node",
                "TypeScript",
                "foo bar",
                "foo;rm -rf /",
                "foo--bar",
                "https://evil.example/pkg.tgz",
            ],
        }
    )

    assert result.data["npm_packages"] == [
        "typescript",
        "@types/node",
        "foo--bar",
    ]


def test_wsl_distribution_filtering():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "wsl_distributions": [
                {"name": "Ubuntu", "version": 2, "state": "Running"},
                {"name": "ubuntu"},
                {"name": "-bad"},
                {"name": "bad name"},
                {"name": "Debian", "version": 3},
                {"name": "Alpine", "version": 1, "state": 5},
                "Ubuntu-20.04",
            ],
        }
    )

    assert result.data["wsl_distributions"] == [
        {"name": "Ubuntu", "version": 2, "state": "Running"},
        {"name": "Alpine", "version": 1},
    ]


def test_extension_ids_are_deduplicated_and_sorted():
    result = validate_setup_payload(
        {
            "applications": [
                {
                    "name": "VS Code",
                    "installed": True,
                    "extensions": [
                        "ms-python.python",
                        "MS-Python.Python",
                        "esbenp.prettier-vscode",
                        "not-an-extension",
                        "bad id",
                        "a.b.c",
                    ],
                }
            ]
        }
    )

    assert result.data["applications"][0]["extensions"] == [
        "a.b.c",
        "esbenp.prettier-vscode",
        "ms-python.python",
    ]


def test_top_level_extensions_merge_into_vs_code_entry():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "applications": [
                {
                    "name": "VS Code",
                    "installed": True,
                    "extensions": ["ms-python.python"],
                }
            ],
            "vscode_extensions": ["esbenp.prettier-vscode"],
        }
    )

    assert result.data["applications"][0]["extensions"] == [
        "esbenp.prettier-vscode",
        "ms-python.python",
    ]
    assert "vscode_extensions" not in result.data


def test_top_level_extensions_are_kept_without_vs_code_entry():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "applications": [],
            "vscode_extensions": [
                "ms-python.python",
                "esbenp.prettier-vscode",
            ],
        }
    )

    assert result.data["vscode_extensions"] == [
        "esbenp.prettier-vscode",
        "ms-python.python",
    ]


def test_environment_variable_filtering():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "environment_variables": {
                "NODE_ENV": "development",
                "PATH": "C:\\Windows",
                "USERPROFILE": "C:\\Users\\alice",
                "DATABASE_PASSWORD": "secret-value",
                "API_KEY": "key-value",
                "HAS SPACE": "value",
                "1INVALID": "value",
                "NUMBER": 42,
                "TOO_LONG": "x" * 4_001,
                "SAFE_VALUE": "ok",
            },
        }
    )

    assert result.data["environment_variables"] == {
        "NODE_ENV": "development",
        "SAFE_VALUE": "ok",
    }

    secrets = result.data["secret_environment_variables"]

    assert "DATABASE_PASSWORD" in secrets
    assert "API_KEY" in secrets
    assert "secret-value" not in str(result.data)
    assert "key-value" not in str(result.data)


def test_declared_secret_names_are_removed_from_values():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "secret_environment_variables": [
                "MY_CUSTOM_VALUE",
                "not valid!",
                "PASSWORD",
            ],
            "environment_variables": {
                "MY_CUSTOM_VALUE": "hidden",
                "PASSWORD": "hidden-too",
            },
        }
    )

    assert result.data["environment_variables"] == {}
    assert result.data["secret_environment_variables"] == [
        "MY_CUSTOM_VALUE",
        "PASSWORD",
    ]


def test_terminal_settings_are_sanitised():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "terminal": {
                "available": True,
                "settings_path": "C:\\Users\\alice\\settings.json",
                "default_profile": "Windows.Terminal.PowershellCore",
                "profiles": [
                    "Windows.Terminal.PowershellCore",
                    "",
                    42,
                ],
                "font_face": "Cascadia Code",
                "color_scheme": "Campbell",
                "message": "ok",
                "unknown": "dropped",
            },
        }
    )

    terminal = result.data["terminal"]

    assert terminal["available"] is True
    assert terminal["profiles"] == [
        "Windows.Terminal.PowershellCore",
    ]
    assert terminal["font_face"] == "Cascadia Code"
    assert "unknown" not in terminal


def test_missing_terminal_gets_defaults():
    result = validate_setup_payload(
        {
            "format_version": 2,
            "applications": [],
        }
    )

    terminal = result.data["terminal"]

    assert terminal["available"] is False
    assert terminal["profiles"] == []
    assert terminal["settings_path"] is None


def test_application_defaults_and_optional_fields():
    result = validate_setup_payload(
        {
            "applications": [
                {"name": "Git", "installed": True},
                {"name": "Slack", "installed": False},
                {"name": "Docker", "installed": True, "version": "4.0"},
            ]
        }
    )

    applications = result.data["applications"]

    assert applications[0] == {
        "name": "Git",
        "version": "Unknown",
        "path": None,
        "installed": True,
    }
    assert applications[1]["version"] == "Not installed"
    assert applications[2]["version"] == "4.0"


def test_payload_must_be_an_object():
    detail = validate_error(["not", "an", "object"])

    assert "data" in detail
    assert "JSON object" in str(detail)


def test_unsupported_format_version():
    detail = validate_error(
        {"format_version": 9, "applications": []}
    )

    assert "data.format_version" in detail
    assert "expected 1 or 2" in str(detail)


def test_format_version_must_be_integer():
    detail = validate_error(
        {"format_version": "2", "applications": []}
    )

    assert "data.format_version" in detail


def test_non_json_values_are_rejected():
    detail = validate_error(
        {"applications": [], "value": object()}
    )

    assert "data" in detail


def test_payload_size_limit():
    detail = validate_error(
        {
            "applications": [],
            "blob": "x" * MAX_SETUP_BYTES,
        }
    )

    assert "2 MB" in str(detail)
