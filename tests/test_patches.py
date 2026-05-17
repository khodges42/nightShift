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


if __name__ == "__main__":
    unittest.main()
