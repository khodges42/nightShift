from pathlib import Path
import tempfile
import unittest

from nightshift.errors import SafetyError
from nightshift.safety import (
    ensure_command_allowed,
    resolve_inside_root,
    resolve_project_root,
    safe_artifact_path,
    validate_scoped_paths,
)


class SafetyTests(unittest.TestCase):
    def test_resolve_project_root_requires_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            self.assertEqual(resolve_project_root(root), root.resolve())

    def test_resolve_inside_root_accepts_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            resolved = resolve_inside_root(root, "src/module.py")

            self.assertEqual(resolved, (root / "src" / "module.py").resolve())

    def test_resolve_inside_root_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(SafetyError, "outside project root"):
                resolve_inside_root(root, "../outside.txt")

    def test_validate_scoped_paths_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(SafetyError, "outside project root"):
                validate_scoped_paths(root, ("src", "../elsewhere"))

    def test_safe_artifact_path_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(SafetyError, "escapes artifact directory"):
                safe_artifact_path(root, ".nightshift", "runs", "..", "..", "leak.txt")

    def test_command_allowlist_accepts_exact_allowed_command(self) -> None:
        command = ensure_command_allowed(
            "python   -m   unittest",
            ("python -m unittest",),
            ("rm -rf", "git push"),
        )

        self.assertEqual(command, "python -m unittest")

    def test_command_allowlist_rejects_unlisted_command(self) -> None:
        with self.assertRaisesRegex(SafetyError, "not allowlisted"):
            ensure_command_allowed("python -m pytest", ("python -m unittest",), ())

    def test_forbidden_fragment_rejects_dangerous_command(self) -> None:
        with self.assertRaisesRegex(SafetyError, "forbidden fragment"):
            ensure_command_allowed("echo ok && rm   -rf build", ("echo ok && rm -rf build",), ("rm -rf",))


if __name__ == "__main__":
    unittest.main()
