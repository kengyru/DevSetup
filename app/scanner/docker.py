import shutil

from app.core.packages import get_package_id
from app.core.versions import extract_version
from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner
from app.scanner.command import ScannerError, run_command


class DockerScanner(BaseScanner):

    NAME = "Docker"
    PACKAGE_ID = get_package_id(NAME)

    def scan(self) -> InstalledApplication:
        docker_path = shutil.which("docker")

        if not docker_path:
            return self.missing()

        try:
            output = run_command(docker_path, ["--version"])
            version = extract_version(output) or output

        except ScannerError:
            version = "Unknown"

        return InstalledApplication(
            name=self.NAME,
            version=version,
            path=docker_path,
            installed=True,
            package_id=self.PACKAGE_ID,
        )
