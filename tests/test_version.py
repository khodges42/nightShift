import subprocess
import sys
import unittest

from nightshift.terminal import format_banner
from nightshift.version import (
    HOTDOG_VERSIONS,
    PACKAGE_VERSION,
    TOPPING_VERSIONS,
    display_version,
    hotdog_version,
    topping_version,
)


class VersionTests(unittest.TestCase):
    def test_display_version_includes_channel_hotdog_and_topping(self) -> None:
        self.assertEqual(display_version(), "0.2.3-alpha-new-york-sport-peppers")
        self.assertEqual(PACKAGE_VERSION, "0.2.3")
        self.assertIn(hotdog_version, HOTDOG_VERSIONS)
        self.assertIn(topping_version, TOPPING_VERSIONS)

    def test_banner_uses_central_display_version(self) -> None:
        self.assertIn(f"VERSION: {display_version()}", format_banner())

    def test_cli_version_uses_central_display_version(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "nightshift.cli", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )

        self.assertEqual(completed.stdout.strip(), f"nightshift {display_version()}")


if __name__ == "__main__":
    unittest.main()
