from pathlib import Path
import tempfile
import unittest

from nightshift.config import SafetyConfig
from nightshift.errors import PipelineError
from nightshift.patches import normalize_patch_text, validate_patch


PATCH = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old
+new
"""


class PatchTests(unittest.TestCase):
    def test_normalize_extracts_fenced_patch(self) -> None:
        text = f"Here it is:\n```diff\n{PATCH}```\n"

        self.assertEqual(normalize_patch_text(text), PATCH)

    def test_validate_patch_enforces_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=("src",),
                allowed_commands=(),
                forbidden_commands=(),
            )

            result = validate_patch(PATCH, root, safety)

            self.assertEqual(result.files, ("src/app.py",))
            self.assertEqual(result.changed_lines, 2)

    def test_validate_patch_rejects_forbidden_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=(".",),
                allowed_commands=(),
                forbidden_commands=(),
            )
            patch = PATCH.replace("src/app.py", ".nightshift/log.txt")

            with self.assertRaisesRegex(PipelineError, "forbidden path"):
                validate_patch(patch, root, safety)

    def test_validate_patch_rejects_malformed_hunk_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=("src",),
                allowed_commands=(),
                forbidden_commands=(),
            )
            patch = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1,2 @@
-old
+new
bare line
"""

            with self.assertRaisesRegex(PipelineError, "malformed hunk line"):
                validate_patch(patch, root, safety)

    def test_validate_patch_rejects_new_file_when_target_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("old\n", encoding="utf-8")
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=("src",),
                allowed_commands=(),
                forbidden_commands=(),
            )
            patch = """diff --git a/src/app.py b/src/app.py
new file mode 100644
--- /dev/null
+++ b/src/app.py
@@ -0,0 +1 @@
+new
"""

            with self.assertRaisesRegex(PipelineError, "creates existing file"):
                validate_patch(patch, root, safety)


if __name__ == "__main__":
    unittest.main()
