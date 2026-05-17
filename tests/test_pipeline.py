from pathlib import Path
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.config import (
    AgentConfig,
    NightShiftConfig,
    PipelineConfig,
    ProjectConfig,
    SafetyConfig,
    StageConfig,
)
from nightshift.pipeline import PipelineRunner
from nightshift.tasks import parse_tasks


TASK_MD = """# Tasks

- [ ] TASK-001: Run fake pipeline

Description:
Exercise a fake pipeline.

Acceptance Criteria:
- Happy path completes
- Artifacts are written
"""


def make_config(root: Path, stages: tuple[StageConfig, ...], max_retries: int = 2) -> NightShiftConfig:
    return NightShiftConfig(
        path=root / "nightshift.yaml",
        project=ProjectConfig(
            name="test",
            root=root,
            task_file=Path("tasks.md"),
            artifact_dir=Path(".nightshift"),
        ),
        safety=SafetyConfig(
            require_clean_worktree=False,
            scoped_paths=(".",),
            allowed_commands=('python -c "print(\'tests ok\')"',),
            forbidden_commands=("rm -rf",),
        ),
        agents={
            "planner": AgentConfig(
                id="planner",
                backend="command",
                command='python -c "print(\'plan ok\')"',
                system_prompt=Path("planner.md"),
            ),
            "reviewer": AgentConfig(
                id="reviewer",
                backend="command",
                command='python -c "print(\'status: pass\\nreason: ok\')"',
                system_prompt=Path("reviewer.md"),
            ),
            "retry_reviewer": AgentConfig(
                id="retry_reviewer",
                backend="command",
                command='python -c "print(\'status: retry\\nreason: retry it\\nnext_stage: implement\')"',
                system_prompt=Path("reviewer.md"),
            ),
        },
        pipeline=PipelineConfig(max_task_retries=max_retries, stages=stages),
    )


class PipelineRunnerTests(unittest.TestCase):
    def test_happy_path_pipeline_completes_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (
                StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),
                StageConfig(
                    id="test",
                    type="command",
                    commands=('python -c "print(\'tests ok\')"',),
                    output="test-output.txt",
                ),
                StageConfig(id="review", type="agent_review", agent="reviewer", output="review.md"),
                StageConfig(id="summarize", type="summarize", output="final-notes.md"),
            )
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            self.assertEqual(result.status, "complete")
            self.assertEqual(result.retry_count, 0)
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "plan.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "stage-results.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "prompts" / "planner.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "run-metadata.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "context.md").exists())
            self.assertTrue((root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "context-out.md").exists())
            self.assertIn(
                "## Task Context",
                (root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "plan.md").read_text(encoding="utf-8"),
            )
            self.assertIn("Modified Files", (root / ".nightshift" / "runs" / "test-run" / "run-summary.md").read_text(encoding="utf-8"))

    def test_review_can_retry_implementation_until_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (
                StageConfig(id="implement", type="agent", agent="planner", output="implementation-log.md"),
                StageConfig(
                    id="review",
                    type="agent_review",
                    agent="retry_reviewer",
                    on_fail="implement",
                    output="review.md",
                ),
            )
            config = make_config(root, stages, max_retries=2)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.retry_count, 2)
            self.assertIn("Retry limit reached", result.reason)
            self.assertEqual([item.stage_id for item in result.stage_results], ["implement", "review", "implement", "review", "implement", "review"])

    def test_stage_error_is_reported_as_failed_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (
                StageConfig(id="plan", type="agent", agent="planner", output="../bad.md"),
            )
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.stage_results[0].status, "fail")
            self.assertTrue(
                (root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "final-notes.md").exists()
            )

    def test_successful_task_is_marked_complete_and_git_artifacts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (
                StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),
            )
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            self.assertEqual(result.status, "complete")
            self.assertIn("- [x] TASK-001", (root / "tasks.md").read_text(encoding="utf-8"))
            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id
            self.assertTrue((task_dir / "task-completion.md").exists())
            self.assertTrue((task_dir / "git-status-before.txt").exists())
            self.assertTrue((task_dir / "git-status-after.txt").exists())
            self.assertTrue((task_dir / "diff.patch").exists())

    def test_multi_task_run_writes_aggregate_summary_and_stops_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            tasks_md = TASK_MD + """

- [ ] TASK-002: Second task

Description:
Should not run after failure.

Acceptance Criteria:
- skipped
"""
            (root / "tasks.md").write_text(tasks_md, encoding="utf-8")
            stages = (
                StageConfig(
                    id="test",
                    type="command",
                    commands=('python -c "print(\'missing\')"',),
                    output="../bad.txt",
                ),
            )
            config = make_config(root, stages, max_retries=0)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            tasks = parse_tasks(tasks_md)

            result = runner.run_tasks(tasks)

            self.assertEqual(result.status, "failed")
            self.assertEqual(len(result.task_results), 1)
            summary = (root / ".nightshift" / "runs" / "test-run" / "run-summary.md").read_text(encoding="utf-8")
            self.assertIn("Tasks run: 1", summary)

    def test_multi_task_run_blocks_incomplete_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            tasks_md = """# Tasks

- [ ] TASK-001: Blocked

Dependencies:
- TASK-002

Acceptance Criteria:
- blocked

- [ ] TASK-002: Later

Acceptance Criteria:
- later
"""
            (root / "tasks.md").write_text(tasks_md, encoding="utf-8")
            config = make_config(root, (), max_retries=0)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_tasks(parse_tasks(tasks_md))

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.task_results[0].status, "blocked")


def _write_common_files(root: Path) -> None:
    (root / "nightshift.yaml").write_text("project:\n  name: test\n", encoding="utf-8")
    (root / "tasks.md").write_text(TASK_MD, encoding="utf-8")
    (root / "planner.md").write_text("Plan.", encoding="utf-8")
    (root / "reviewer.md").write_text("Review.", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
