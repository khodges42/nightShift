from pathlib import Path
import tempfile
import unittest

from nightshift.config import SafetyConfig
from nightshift.errors import PipelineError
from nightshift.patches import (
    generate_patch_from_file_updates,
    normalize_patch_text,
    parse_file_updates,
    repair_hunk_counts,
    validate_patch,
)


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

    def test_validate_patch_rejects_hunk_count_mismatch(self) -> None:
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
"""

            with self.assertRaisesRegex(PipelineError, "new line count expected 2, got 1"):
                validate_patch(patch, root, safety)

    def test_normalize_repairs_hunk_count_mismatch(self) -> None:
        lines = "\n".join(f"+line {number}" for number in range(38))
        patch = f"""diff --git a/src/app.py b/src/app.py
--- /dev/null
+++ b/src/app.py
@@ -0,0 +1,40 @@
{lines}
"""

        normalized = normalize_patch_text(patch)

        self.assertIn("@@ -0,0 +1,38 @@", normalized)

    def test_validate_patch_counts_hunk_lines_that_look_like_headers(self) -> None:
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
@@ -1,3 +1,3 @@
 context
---
----
+++
++++
"""

            result = validate_patch(patch, root, safety)

            self.assertEqual(result.changed_lines, 4)

    def test_repair_hunk_counts_counts_header_like_body_lines(self) -> None:
        patch = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
 context
---
+++
"""

        repaired = repair_hunk_counts(patch)

        self.assertIn("@@ -1,2 +1,2 @@", repaired)

    def test_validate_patch_accepts_multiple_files(self) -> None:
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
@@ -1 +1 @@
-old
+new
diff --git a/src/test_app.py b/src/test_app.py
--- a/src/test_app.py
+++ b/src/test_app.py
@@ -1 +1 @@
-old test
+new test
"""

            result = validate_patch(patch, root, safety)

            self.assertEqual(result.files, ("src/app.py", "src/test_app.py"))

    def test_file_updates_generate_unified_diff(self) -> None:
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
            updates = parse_file_updates(
                """```file:src/app.py
new
```
```file:src/test_app.py
test
```
"""
            )

            patch = generate_patch_from_file_updates(updates, root, safety)
            result = validate_patch(patch, root, safety)

            self.assertIn("diff --git a/src/app.py b/src/app.py", patch)
            self.assertIn("diff --git a/src/test_app.py b/src/test_app.py", patch)
            self.assertIn("new file mode 100644", patch)
            self.assertEqual(result.files, ("src/app.py", "src/test_app.py"))

    def test_file_updates_reject_duplicate_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=(".",),
                allowed_commands=(),
                forbidden_commands=(),
            )
            updates = parse_file_updates(
                """```file:app.py
one
```
```file:app.py
two
```
"""
            )

            with self.assertRaisesRegex(PipelineError, "duplicate file block"):
                generate_patch_from_file_updates(updates, root, safety)


if __name__ == "__main__":
    unittest.main()
