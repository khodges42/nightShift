from pathlib import Path
import tempfile
import unittest

from nightshift.errors import InitError
from nightshift.init import init_project


class InitProjectTests(unittest.TestCase):
    def test_init_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            written = init_project(root)

            self.assertIn(root / "nightshift.yaml", written)
            self.assertTrue((root / "nightshift.yaml").exists())
            self.assertTrue((root / "tasks.md").exists())
            self.assertTrue((root / "agents" / "planner.md").exists())
            self.assertTrue((root / "agents" / "implementer.md").exists())
            self.assertTrue((root / "agents" / "reviewer.md").exists())

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)

            with self.assertRaises(InitError):
                init_project(root)

    def test_init_can_overwrite_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            (root / "tasks.md").write_text("changed", encoding="utf-8")

            init_project(root, force=True)

            self.assertIn("TASK-001", (root / "tasks.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
