from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.config import SafetyConfig
from nightshift.repo_tools import RepoTools, parse_lookup_requests


class RepoToolsTests(unittest.TestCase):
    def test_repo_tools_are_scoped_and_line_numbered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=("src",),
                allowed_commands=(),
                forbidden_commands=(),
            )
            tools = RepoTools(root, safety, ArtifactStore(root, ".nightshift", run_id="test-run"))

            self.assertIn("src/app.py", tools.list_files("src", "*.py"))
            self.assertIn("1: def hello():", tools.read_file("src/app.py"))
            self.assertIn("src/app.py:1", tools.grep("hello", "src"))

    def test_parse_lookup_requests(self) -> None:
        output = """Plan needs context.

lookup_requests:
- tool: read_file
  path: nightshift/pipeline.py
- tool: grep
  path: nightshift
  pattern: PipelineRunner
"""

        requests = parse_lookup_requests(output)

        self.assertEqual([request.name for request in requests], ["read_file", "grep"])
        self.assertEqual(requests[0].arguments["path"], "nightshift/pipeline.py")
        self.assertEqual(requests[1].arguments["pattern"], "PipelineRunner")

    def test_parse_lookup_requests_dedupes_and_caps(self) -> None:
        repeated = "\n".join(
            [
                "lookup_requests:",
                *[
                    "- tool: grep\n  path: .\n  pattern: parse.*tokenize"
                    for _ in range(20)
                ],
                "- tool: read_file\n  path: lisp.py",
            ]
        )

        requests = parse_lookup_requests(repeated)

        self.assertEqual(len(requests), 2)
        self.assertEqual([request.name for request in requests], ["grep", "read_file"])

    def test_repo_tools_skip_artifact_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".nightshift" / "runs").mkdir(parents=True)
            (root / ".nightshift" / "runs" / "run.log").write_text("needle\n", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("needle\n", encoding="utf-8")
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=(".",),
                allowed_commands=(),
                forbidden_commands=(),
            )
            tools = RepoTools(root, safety, ArtifactStore(root, ".nightshift", run_id="test-run"))

            files = tools.list_files(".")
            matches = tools.grep("needle", ".")

            self.assertIn("src/app.py", files)
            self.assertNotIn(".nightshift", files)
            self.assertIn("src/app.py:1", matches)
            self.assertNotIn(".nightshift", matches)


if __name__ == "__main__":
    unittest.main()
