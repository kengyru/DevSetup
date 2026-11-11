from app.core.versions import has_version, versions_match
from app.models.application import InstalledApplication
from app.models.comparison import ComparisonItem, ComparisonStatus


class CompareService:
    """Compares the saved setup (desired state) with the current PC.

    The saved setup describes what the user wants to have. The current PC
    describes what actually exists. An application is missing when it is not
    installed on the current PC, no matter what the saved entry says.
    """

    def compare(
        self,
        saved_applications: list[InstalledApplication],
        current_applications: list[InstalledApplication],
    ) -> list[ComparisonItem]:

        current_by_name: dict[str, InstalledApplication] = {}

        for application in current_applications:
            key = application.name.strip().lower()
            current_by_name.setdefault(key, application)

        result: list[ComparisonItem] = []

        for saved in saved_applications:
            current = current_by_name.get(
                saved.name.strip().lower()
            )

            if current is None or not current.installed:
                status = ComparisonStatus.MISSING

            elif not has_version(saved.version):
                # The setup only says "this tool is wanted", so its
                # presence is enough and versions cannot be compared.
                status = ComparisonStatus.INSTALLED

            elif versions_match(
                saved.version,
                current.version,
            ):
                status = ComparisonStatus.INSTALLED

            else:
                status = ComparisonStatus.VERSION_MISMATCH

            result.append(
                ComparisonItem(
                    saved=saved,
                    current=current,
                    status=status,
                )
            )

        return result
