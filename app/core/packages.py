"""Known winget package identifiers for the tools DevSetup understands."""

PACKAGE_IDS = {
    "python": "Python.Python.3.13",
    "git": "Git.Git",
    "vs code": "Microsoft.VisualStudioCode",
    "docker": "Docker.DockerDesktop",
    "postgresql": "PostgreSQL.PostgreSQL",
}


def get_package_id(application_name: str) -> str | None:
    """Return the winget package id for an application name, if known."""

    if not application_name:
        return None

    return PACKAGE_IDS.get(application_name.strip().lower())
