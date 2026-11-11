"""Detection of secrets and system-managed environment variables.

DevSetup must never write passwords, tokens or API keys into a setup file.
The checks are name based: a value is never inspected, only the variable
name. False positives are acceptable (the variable is then skipped and
shown to the user), false negatives are not.
"""

import re

_SECRET_TOKENS = {
    "PASSWORD",
    "PASSWD",
    "PASSPHRASE",
    "PASS",
    "PWD",
    "SECRET",
    "SECRETS",
    "TOKEN",
    "TOKENS",
    "CREDENTIAL",
    "CREDENTIALS",
    "COOKIE",
    "COOKIES",
    "APIKEY",
    "PRIVATEKEY",
    "ACCESSKEY",
    "SIGNINGKEY",
    "KEY",
    "AUTH",
    "OAUTH",
    "PAT",
    "DSN",
    "BEARER",
    "SALT",
}

_SECRET_PAIRS = {
    ("API", "KEY"),
    ("ACCESS", "KEY"),
    ("PRIVATE", "KEY"),
    ("SIGNING", "KEY"),
    ("CLIENT", "SECRET"),
    ("CONNECTION", "STRING"),
}

_SECRET_MARKERS = (
    "APIKEY",
    "ACCESSTOKEN",
    "REFRESHTOKEN",
    "PRIVATEKEY",
    "SECRETKEY",
    "PASSWORD",
    "CONNECTIONSTRING",
    "CREDENTIALS",
)

_PROTECTED_NORMALIZED = {
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "COMSPEC",
    "SYSTEMROOT",
    "WINDIR",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILESX86",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILESX86",
    "USERNAME",
    "USERDOMAIN",
    "COMPUTERNAME",
    "OS",
    "NUMBEROFPROCESSORS",
    "PSMODULEPATH",
    "VIRTUALENV",
    "CONDAPREFIX",
    "PYTHONHOME",
}


def _tokens(name: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^A-Za-z0-9]+", name.upper())
        if token
    ]


def _normalize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()


def is_secret_name(name: str) -> bool:
    """Return True when the variable name looks like a secret."""

    if not name:
        return False

    tokens = _tokens(name)

    if any(token in _SECRET_TOKENS for token in tokens):
        return True

    for first, second in zip(tokens, tokens[1:]):
        if (first, second) in _SECRET_PAIRS:
            return True

    normalized = _normalize(name)

    if any(marker in normalized for marker in _SECRET_MARKERS):
        return True

    if "URL" in normalized or "URI" in normalized:
        if any(
            part in normalized
            for part in (
                "DATABASE",
                "DB",
                "MONGO",
                "REDIS",
                "AMQP",
                "BROKER",
                "CONNECTION",
            )
        ):
            return True

    return False


def is_protected_name(name: str) -> bool:
    """Return True for system-managed variables we must not restore."""

    normalized = _normalize(name)

    if normalized in _PROTECTED_NORMALIZED:
        return True

    return normalized.startswith("PROCESSOR")


def is_safe_environment_name(name: str) -> bool:
    """Return True when the variable may be saved and restored."""

    if not name:
        return False

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return False

    if is_secret_name(name):
        return False

    return not is_protected_name(name)
