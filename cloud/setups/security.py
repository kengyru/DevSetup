"""Name based detection of secret environment variables.

The backend must not store secrets even when a client sends them. The
checks below are an independent copy of the desktop rules (the backend
never imports the desktop package). Only variable *names* are inspected,
never values. False positives are acceptable; false negatives are not.
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

_SAFE_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


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
    """Return True for system-managed variables that must not be stored."""

    normalized = _normalize(name)

    if normalized in _PROTECTED_NORMALIZED:
        return True

    return normalized.startswith("PROCESSOR")


def is_valid_environment_name(name: str) -> bool:
    return (
        isinstance(name, str)
        and _SAFE_NAME_RE.fullmatch(name) is not None
    )


def is_safe_environment_name(name: str) -> bool:
    """Return True when the variable may be stored and restored."""

    if not is_valid_environment_name(name):
        return False

    if is_secret_name(name):
        return False

    return not is_protected_name(name)
