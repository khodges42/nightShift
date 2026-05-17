from pathlib import Path
from dataclasses import replace
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

    def test_run_writes_operational_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            config = make_config(root, stages)
            runner = PipelineRunner(config, artifacts)
            task = parse_tasks(TASK_MD)[0]
            artifacts.initialize_run()
            artifacts.run_log_path.write_text("old run log\n", encoding="utf-8")

            runner.run_task(task)

            log = (root / ".nightshift" / "runs" / "test-run" / "run.log").read_text(encoding="utf-8")
            self.assertNotIn("old run log", log)
            self.assertIn("task.start", log)
            self.assertIn("stage.start", log)
            self.assertIn("agent.finish", log)

    def test_planner_lookup_requests_write_files_inspected_and_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "fake_planner.py").write_text(
                "\n".join(
                    [
                        "import sys",
                        "prompt = sys.stdin.read()",
                        "if 'repo_lookup_results' in prompt:",
                        "    print('final plan with context')",
                        "else:",
                        "    print('lookup_requests:')",
                        "    print('- tool: read_file')",
                        "    print('  path: target.py')",
                    ]
                ),
                encoding="utf-8",
            )
            stages = (StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),)
            config = make_config(root, stages)
            config.agents["planner"] = AgentConfig(
                id="planner",
                backend="command",
                command="python fake_planner.py",
                system_prompt=Path("planner.md"),
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id
            self.assertEqual(result.status, "complete")
            self.assertTrue((task_dir / "files-inspected.md").exists())
            self.assertIn("1: VALUE = 1", (task_dir / "files-inspected.md").read_text(encoding="utf-8"))
            self.assertIn("final plan with context", (task_dir / "plan.md").read_text(encoding="utf-8"))

    def test_repo_context_stage_writes_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "app.py").write_text("def run_pipeline():\n    return True\n", encoding="utf-8")
            stages = (StageConfig(id="context", type="repo_context", output="context-pack.md"),)
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            pack = root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id / "context-pack.md"
            self.assertEqual(result.status, "complete")
            self.assertIn("Context Pack", pack.read_text(encoding="utf-8"))
            self.assertIn("app.py", pack.read_text(encoding="utf-8"))

    def test_project_context_chart_is_written_during_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "cli.py").write_text(
                "def main():\n    return 0\n\nif __name__ == \"__main__\":\n    main()\n",
                encoding="utf-8",
            )
            stages = (StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),)
            config = make_config(root, stages)
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            runner.run_task(task)

            chart = root / ".nightshift" / "project-context-chart.md"
            self.assertTrue(chart.exists())
            content = chart.read_text(encoding="utf-8")
            self.assertIn("cli.py", content)
            self.assertIn("main@L1", content)

    def test_code_writer_normalizer_and_validator_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "app.py").write_text("old\n", encoding="utf-8")
            (root / "fake_writer.py").write_text(
                "\n".join(
                    [
                        "print('```diff')",
                        "print('diff --git a/app.py b/app.py')",
                        "print('--- a/app.py')",
                        "print('+++ b/app.py')",
                        "print('@@ -1 +1 @@')",
                        "print('-old')",
                        "print('+new')",
                        "print('```')",
                    ]
                ),
                encoding="utf-8",
            )
            stages = (
                StageConfig(id="context", type="repo_context", output="context-pack.md"),
                StageConfig(id="write", type="code_writer", agent="writer"),
                StageConfig(id="normalize", type="patch_normalizer"),
                StageConfig(id="validate", type="patch_validator"),
            )
            config = make_config(root, stages)
            config.agents["writer"] = AgentConfig(
                id="writer",
                backend="command",
                command="python fake_writer.py",
                system_prompt=Path("planner.md"),
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))
            task = parse_tasks(TASK_MD)[0]

            result = runner.run_task(task)

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / task.id
            self.assertEqual(result.status, "complete")
            self.assertTrue((task_dir / "proposed.patch").exists())
            self.assertTrue((task_dir / "implementation-summary.md").exists())
            self.assertTrue((task_dir / "normalized.patch").exists())
            self.assertIn("Status: pass", (task_dir / "patch-validation.md").read_text(encoding="utf-8"))

    def test_patch_validator_rejects_unsafe_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            stages = (
                StageConfig(id="write", type="code_writer", agent="writer"),
                StageConfig(id="validate", type="patch_validator"),
            )
            (root / "fake_writer.py").write_text(
                "\n".join(
                    [
                        "print('diff --git a/.nightshift/log.txt b/.nightshift/log.txt')",
                        "print('--- a/.nightshift/log.txt')",
                        "print('+++ b/.nightshift/log.txt')",
                        "print('@@ -1 +1 @@')",
                        "print('-old')",
                        "print('+new')",
                    ]
                ),
                encoding="utf-8",
            )
            config = make_config(root, stages)
            config.agents["writer"] = AgentConfig(
                id="writer",
                backend="command",
                command="python fake_writer.py",
                system_prompt=Path("planner.md"),
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            self.assertEqual(result.status, "failed")
            self.assertIn("forbidden path", result.reason)

    def test_patch_apply_stage_applies_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "app.py").write_text("old\n", encoding="utf-8")
            (root / "fake_writer.py").write_text(
                "\n".join(
                    [
                        "print('diff --git a/app.py b/app.py')",
                        "print('--- a/app.py')",
                        "print('+++ b/app.py')",
                        "print('@@ -1 +1 @@')",
                        "print('-old')",
                        "print('+new')",
                    ]
                ),
                encoding="utf-8",
            )
            stages = (
                StageConfig(id="write", type="code_writer", agent="writer"),
                StageConfig(id="normalize", type="patch_normalizer"),
                StageConfig(id="validate", type="patch_validator"),
                StageConfig(id="apply", type="patch_apply", mode="apply"),
            )
            config = make_config(root, stages)
            config.agents["writer"] = AgentConfig(
                id="writer",
                backend="command",
                command="python fake_writer.py",
                system_prompt=Path("planner.md"),
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            self.assertEqual(result.status, "complete")
            self.assertEqual((root / "app.py").read_text(encoding="utf-8"), "new\n")
            self.assertTrue((task_dir / "applied.patch").exists())
            self.assertTrue((task_dir / "patch-apply-output.txt").exists())
            self.assertTrue((task_dir / "git-status-before-patch-apply.txt").exists())
            self.assertTrue((task_dir / "git-status-after-patch-apply.txt").exists())

    def test_test_failure_repairs_with_second_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "app.py").write_text("old\n", encoding="utf-8")
            (root / "fake_writer.py").write_text(
                "\n".join(
                    [
                        "from pathlib import Path",
                        "current = Path('app.py').read_text()",
                        "old, new = ('bad', 'new') if current == 'bad\\n' else ('old', 'bad')",
                        "print('diff --git a/app.py b/app.py')",
                        "print('--- a/app.py')",
                        "print('+++ b/app.py')",
                        "print('@@ -1 +1 @@')",
                        "print('-' + old)",
                        "print('+' + new)",
                    ]
                ),
                encoding="utf-8",
            )
            test_command = 'python -c "from pathlib import Path; raise SystemExit(0 if Path(\'app.py\').read_text().strip() == \'new\' else 1)"'
            stages = (
                StageConfig(id="write", type="code_writer", agent="writer"),
                StageConfig(id="normalize", type="patch_normalizer"),
                StageConfig(id="validate", type="patch_validator"),
                StageConfig(id="apply", type="patch_apply", mode="apply"),
                StageConfig(
                    id="test",
                    type="command",
                    commands=(test_command,),
                    output="test-output.txt",
                    on_fail="write",
                ),
            )
            config = make_config(
                root,
                stages,
                max_retries=1,
            )
            config = replace(
                config,
                safety=SafetyConfig(
                    require_clean_worktree=False,
                    scoped_paths=(".",),
                    allowed_commands=(test_command,),
                    forbidden_commands=("rm -rf",),
                ),
            )
            config.agents["writer"] = AgentConfig(
                id="writer",
                backend="command",
                command="python fake_writer.py",
                system_prompt=Path("planner.md"),
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.retry_count, 1)
            self.assertEqual((root / "app.py").read_text(encoding="utf-8"), "new\n")
            self.assertTrue((task_dir / "repair-1.patch").exists())
            self.assertTrue((task_dir / "repair-summary-1.md").exists())


def _write_common_files(root: Path) -> None:
    (root / "nightshift.yaml").write_text("project:\n  name: test\n", encoding="utf-8")
    (root / "tasks.md").write_text(TASK_MD, encoding="utf-8")
    (root / "planner.md").write_text("Plan.", encoding="utf-8")
    (root / "reviewer.md").write_text("Review.", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
