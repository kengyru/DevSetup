import shutil

from app.core.process import run_process
from app.scanner.base import BaseCollector


# Only these settings are saved and restored. Everything else (credentials,
# credential helpers, URL rewrites that may contain tokens, signing keys,
# aliases that execute shell commands) is ignored on purpose.
SAFE_GIT_KEYS = frozenset(
    {
        "user.name",
        "user.email",
        "core.editor",
        "core.autocrlf",
        "core.eol",
        "init.defaultbranch",
        "pull.rebase",
        "pull.ff",
        "push.default",
        "push.autosetupremote",
        "merge.conflictstyle",
        "fetch.prune",
    }
)


def is_safe_git_key(key: str) -> bool:
    if not isinstance(key, str) or not key.strip():
        return False

    return key.strip().lower() in SAFE_GIT_KEYS


def parse_git_config(output: str) -> dict[str, str]:
    """Parse `git config --global --list`, keeping safe keys only."""

    settings: dict[str, str] = {}

    for line in output.splitlines():
        key, separator, value = line.partition("=")

        if not separator:
            continue

        key = key.strip().lower()

        if not is_safe_git_key(key):
            continue

        settings[key] = value

    return settings


class GitConfigScanner(BaseCollector):
    """Reads the safe part of the global Git configuration."""

    NAME = "Git configuration"

    def scan(self) -> dict[str, str]:
        git_path = shutil.which("git")

        if not git_path:
            self.available = False
            return {}

        result = run_process(
            [git_path, "config", "--global", "--list"],
            timeout=30,
        )

        if result.returncode != 0:
            # No global config yet is not an error.
            return {}

        return parse_git_config(result.output)


def get_safe_git_settings(
    settings: dict[str, str],
) -> dict[str, str]:
    return {
        key: value
        for key, value in settings.items()
        if is_safe_git_key(key)
        and isinstance(value, str)
    }
