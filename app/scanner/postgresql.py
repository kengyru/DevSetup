import shutil

from app.core.packages import get_package_id
from app.core.versions import extract_version
from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner
from app.scanner.command import ScannerError, run_command


class PostgreSQLScanner(BaseScanner):

    NAME = "PostgreSQL"
    PACKAGE_ID = get_package_id(NAME)

    def scan(self) -> InstalledApplication:
        postgres_path = shutil.which("psql")

        if not postgres_path:
            return self.missing()

        try:
            output = run_command(postgres_path, ["--version"])
            version = extract_version(output) or output

        except ScannerError:
            version = "Unknown"

        return InstalledApplication(
            name=self.NAME,
            version=version,
            path=postgres_path,
            installed=True,
            package_id=self.PACKAGE_ID,
        )
