import unittest

from app.core.versions import extract_version, versions_match
from app.models.application import InstalledApplication
from app.models.comparison import ComparisonStatus
from app.services.compare_service import CompareService


class VersionHelperTests(unittest.TestCase):

    def test_extract_version_from_tool_output(self):
        self.assertEqual(
            extract_version("Python 3.13.16"),
            "3.13.16",
        )
        self.assertEqual(
            extract_version("git version 2.56.0.windows.2"),
            "2.56.0",
        )
        self.assertEqual(extract_version("1.142.0"), "1.142.0")

    def test_extract_version_without_numbers(self):
        self.assertEqual(
            extract_version("Unknown"),
            "Unknown",
        )

    def test_versions_match_ignores_prefixes(self):
        self.assertTrue(
            versions_match("3.13.16", "Python 3.13.16")
        )
        self.assertFalse(
            versions_match("3.13.16", "Python 3.13.15")
        )


class CompareServiceTests(unittest.TestCase):

    def setUp(self):
        self.service = CompareService()

    def compare(self, saved, current):
        return self.service.compare(
            saved_applications=saved,
            current_applications=current,
        )

    def test_same_version_is_installed(self):
        saved = [
            InstalledApplication(
                "Python", "3.13.16", r"C:\Python\python.exe", True
            )
        ]
        current = [
            InstalledApplication(
                "Python",
                "Python 3.13.16",
                r"C:\Python\python.exe",
                True,
            )
        ]

        item = self.compare(saved, current)[0]

        self.assertIs(item.status, ComparisonStatus.INSTALLED)
        self.assertEqual(
            item.current_version,
            "Python 3.13.16",
        )

    def test_not_installed_on_pc_is_missing(self):
        # The old bug: a current entry with installed=False was
        # treated as installed just because the name was present.
        saved = [
            InstalledApplication(
                "Docker", "27.0.3", None, True
            )
        ]
        current = [
            InstalledApplication(
                "Docker", "Not installed", None, False
            )
        ]

        item = self.compare(saved, current)[0]

        self.assertIs(item.status, ComparisonStatus.MISSING)
        self.assertEqual(item.current_version, "Not installed")
        self.assertIsNone(item.current_path)

    def test_absent_from_current_is_missing(self):
        saved = [
            InstalledApplication(
                "PostgreSQL", "16.4", None, True
            )
        ]

        item = self.compare(saved, [])[0]

        self.assertIs(item.status, ComparisonStatus.MISSING)
        self.assertIsNone(item.current)

    def test_saved_missing_app_is_still_desired(self):
        # A setup may store an application the user wants but did
        # not have when the setup was saved. Once it appears on the
        # PC, there is nothing left to restore.
        saved = [
            InstalledApplication(
                "Docker", "Not installed", None, False
            )
        ]
        current = [
            InstalledApplication(
                "Docker", "27.0.3", r"C:\Docker", True
            )
        ]

        item = self.compare(saved, current)[0]

        self.assertIs(item.status, ComparisonStatus.INSTALLED)

    def test_saved_unknown_version_is_installed_if_present(self):
        saved = [InstalledApplication("Docker", "Unknown", None, True)]
        current = [
            InstalledApplication("Docker", "27.0.3", None, True)
        ]

        item = self.compare(saved, current)[0]

        self.assertIs(item.status, ComparisonStatus.INSTALLED)

    def test_different_versions_are_mismatch(self):
        saved = [InstalledApplication("Git", "2.56.0", None, True)]
        current = [
            InstalledApplication(
                "Git",
                "git version 2.40.1.windows.1",
                r"C:\Git\git.exe",
                True,
            )
        ]

        item = self.compare(saved, current)[0]

        self.assertIs(
            item.status,
            ComparisonStatus.VERSION_MISMATCH,
        )
        self.assertEqual(item.current_version, current[0].version)

    def test_name_matching_is_case_insensitive(self):
        saved = [InstalledApplication("VS Code", "1.142.0", None, True)]
        current = [
            InstalledApplication(
                "vs code", "1.142.0", None, True
            )
        ]

        item = self.compare(saved, current)[0]

        self.assertIs(item.status, ComparisonStatus.INSTALLED)

    def test_result_follows_saved_order(self):
        saved = [
            InstalledApplication("Git", "1.0", None, True),
            InstalledApplication("Python", "3.13", None, True),
        ]
        current = [
            InstalledApplication("Python", "3.13", None, True),
            InstalledApplication("Git", "1.0", None, True),
        ]

        result = self.compare(saved, current)

        self.assertEqual(
            [item.saved.name for item in result],
            ["Git", "Python"],
        )


if __name__ == "__main__":
    unittest.main()
