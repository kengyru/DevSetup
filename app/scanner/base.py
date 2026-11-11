from abc import ABC, abstractmethod
from typing import Optional

from app.models.application import InstalledApplication


class BaseScanner(ABC):
    """Base class for a tool scanner.

    Subclasses set NAME and PACKAGE_ID and implement scan().
    """

    NAME: str = ""
    PACKAGE_ID: Optional[str] = None

    @abstractmethod
    def scan(self) -> InstalledApplication:
        """Return the current state of the tool on this PC."""

    def missing(self) -> InstalledApplication:
        """Build the result used when the tool is not installed."""

        return InstalledApplication(
            name=self.NAME,
            version="Not installed",
            path=None,
            installed=False,
            package_id=self.PACKAGE_ID,
        )


class BaseCollector(ABC):
    """Base class for scanners of extra developer data.

    Collectors return domain values (list, dict, TerminalSettings, ...)
    instead of InstalledApplication. Each collector exposes `available`
    so the UI can tell "not installed" apart from "nothing saved".
    """

    NAME: str = ""

    def __init__(self):
        self.available = True

    @abstractmethod
    def scan(self) -> object:
        """Read the current state and return it."""
