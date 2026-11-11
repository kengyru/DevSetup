from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner


class ScanService:
    """Runs every scanner and keeps going even if one of them fails."""

    def __init__(self, scanners: list[BaseScanner]):
        self.scanners = scanners
        self.errors: list[str] = []

    def scan(self) -> list[InstalledApplication]:
        self.errors = []

        results = []

        for scanner in self.scanners:
            try:
                results.append(scanner.scan())

            except Exception as error:
                name = getattr(
                    scanner,
                    "NAME",
                    scanner.__class__.__name__,
                )

                self.errors.append(f"{name}: {error}")

                results.append(
                    InstalledApplication(
                        name=name,
                        version="Unknown",
                        path=None,
                        installed=False,
                        package_id=getattr(
                            scanner,
                            "PACKAGE_ID",
                            None,
                        ),
                    )
                )

        return results
