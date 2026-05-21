from pathlib import Path
from dataclasses import replace
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.config import SafetyConfig, StageConfig
from nightshift.pipeline import PipelineRunner
from nightshift.semantic_index import build_semantic_index, search_index
from nightshift.tasks import parse_tasks
from nightshift.telemetry import estimate_tokens, format_telemetry_summary, telemetry_from_stage_output

from tests.test_pipeline import TASK_MD, make_config, _write_common_files


class TelemetryAndIndexTests(unittest.TestCase):
    def test_telemetry_estimates_tokens_and_groups_by_model(self) -> None:
        output = "\n".join(
            [
                "# Agent Output: plan",
                "",
                "Agent: `planner`",
                "Duration seconds: 1.250",
                "",
                "## stdout",
                "",
                "```text",
                "plan ok",
                "```",
                "",
                "## Prompt",
                "",
                "```markdown",
                "hello world",
                "```",
            ]
        )

        entry = telemetry_from_stage_output(
            stage_id="plan",
            stage_type="agent",
            status="pass",
            output=output,
            retry_count=0,
            model="qwen2.5-coder:14b",
        )
        summary = format_telemetry_summary((entry,))

        self.assertGreater(estimate_tokens("hello world"), 0)
        self.assertEqual(entry.agent_id, "planner")
        self.assertEqual(entry.duration_seconds, 1.25)
        self.assertIn("qwen2.5-coder:14b", summary)

    def test_pipeline_writes_telemetry_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),)
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            self.assertEqual(result.status, "complete")
            self.assertTrue((task_dir / "telemetry-summary.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "telemetry-summary.md").exists())

    def test_semantic_index_finds_symbols_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "demo.egg-info").mkdir()
            (root / "src" / "service.py").write_text(
                "import sqlite3\n\nclass SnippetStore:\n    pass\n\ndef create_snippet():\n    return True\n",
                encoding="utf-8",
            )
            (root / "src" / "demo.egg-info" / "PKG-INFO").write_text(
                "Name: generated-metadata\n",
                encoding="utf-8",
            )
            (root / "tests" / "test_service.py").write_text(
                "def test_create_snippet():\n    assert True\n",
                encoding="utf-8",
            )
            safety = SafetyConfig(
                require_clean_worktree=False,
                scoped_paths=("src", "tests"),
                allowed_commands=(),
                forbidden_commands=(),
            )

            index = build_semantic_index(root, safety)
            results = search_index(index, "create snippet sqlite")

            self.assertTrue(any("create_snippet" in item.symbols for item in index))
            self.assertTrue(any(item.path == "src/service.py" for item in results))
            self.assertFalse(any(".egg-info" in item.path for item in index))

    def test_semantic_context_stage_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "snippet.py").write_text("def create_snippet():\n    return 'ok'\n", encoding="utf-8")
            stages = (StageConfig(id="semantic", type="semantic_context", output="semantic-context.md"),)
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            self.assertEqual(result.status, "complete")
            self.assertTrue((task_dir / "semantic-index.md").exists())
            self.assertTrue((task_dir / "semantic-context.md").exists())

    def test_semantic_context_prefers_current_task_test_and_excludes_future_task_tests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "tests").mkdir(exist_ok=True)
            (root / "tests" / "test_task001.py").write_text(
                "def test_create_snippet_returns_id():\n    assert True\n",
                encoding="utf-8",
            )
            (root / "tests" / "test_task002.py").write_text(
                "def test_create_snippet_accepts_language_and_tags():\n    assert True\n",
                encoding="utf-8",
            )
            stages = (StageConfig(id="semantic", type="semantic_context", output="semantic-context.md"),)
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            context = (task_dir / "semantic-context.md").read_text(encoding="utf-8")
            self.assertEqual(result.status, "complete")
            self.assertIn("## `tests/test_task001.py`", context)
            self.assertNotIn("## `tests/test_task002.py`", context)

    def test_repo_context_excludes_future_task_test_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "tests").mkdir(exist_ok=True)
            (root / "tests" / "test_task001.py").write_text(
                "def test_create_snippet_returns_id():\n    assert True\n",
                encoding="utf-8",
            )
            (root / "tests" / "test_task002.py").write_text(
                "def test_create_snippet_accepts_language_and_tags():\n    assert True\n",
                encoding="utf-8",
            )
            task_md = """# Tasks

- [ ] TASK-001: Snippet creation

Description:
Create snippets.

Acceptance Criteria:
- POST /snippets creates a snippet
"""
            stages = (StageConfig(id="context", type="repo_context", output="context-pack.md"),)
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(task_md)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            context = (task_dir / "context-pack.md").read_text(encoding="utf-8")
            self.assertEqual(result.status, "complete")
            self.assertIn("tests/test_task001.py", context)
            self.assertNotIn("tests/test_task002.py", context)


if __name__ == "__main__":
    unittest.main()
