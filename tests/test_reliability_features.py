from pathlib import Path
from dataclasses import replace
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.config import parse_config, StageConfig
from nightshift.failures import classify_failure
from nightshift.integ import cleanup_integration_runs, create_integration_run
from nightshift.patches import validate_patch
from nightshift.pipeline import PipelineRunner
from nightshift.tasks import parse_tasks

from tests.test_pipeline import TASK_MD, make_config, _write_common_files


class ReliabilityFeatureTests(unittest.TestCase):
    def test_failure_classifier_detects_missing_dependency(self) -> None:
        result = classify_failure("ModuleNotFoundError: No module named 'flask'", exit_code=1)

        self.assertEqual(result.category, "missing dependency")
        self.assertIn("flask", result.probable_root_cause)
        self.assertIn("do not retry", result.retry_recommendation)

    def test_command_failure_writes_diagnostics_and_retry_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            command = 'python -c "raise AssertionError(\'expected value\')"'
            stages = (
                StageConfig(
                    id="test",
                    type="command",
                    commands=(command,),
                    output="test-output.txt",
                    on_fail="plan",
                ),
                StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),
            )
            config = make_config(root, stages, max_retries=1)
            config = replace(
                config,
                safety=replace(config.safety, allowed_commands=(command,)),
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            self.assertEqual(result.status, "complete")
            self.assertTrue((task_dir / "diagnostics" / "test-failure.md").exists())
            self.assertTrue((task_dir / "retry-memory.md").exists())
            self.assertTrue((task_dir / "escalation-policy.md").exists())
            self.assertIn("test expectation mismatch", (task_dir / "diagnostics" / "test-failure.md").read_text(encoding="utf-8"))

    def test_agent_blocked_request_generates_run_local_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_common_files(root)
            (root / "fake_agent.py").write_text(
                "print('blocked_request: json fixtures/input.json missing json fixture')\n",
                encoding="utf-8",
            )
            stages = (StageConfig(id="plan", type="agent", agent="planner", output="plan.md"),)
            config = make_config(root, stages)
            config.agents["planner"] = replace(
                config.agents["planner"],
                command="python fake_agent.py",
            )
            runner = PipelineRunner(config, ArtifactStore(root, ".nightshift", run_id="test-run"))

            result = runner.run_task(parse_tasks(TASK_MD)[0])

            task_dir = root / ".nightshift" / "runs" / "test-run" / "tasks" / "TASK-001"
            self.assertEqual(result.status, "complete")
            self.assertTrue((task_dir / "resources" / "fixtures" / "input.json").exists())
            self.assertTrue((task_dir / "resource-requests.md").exists())

    def test_config_parses_agent_pool_and_delete_ratio(self) -> None:
        root = Path.cwd()
        raw = {
            "project": {"name": "x", "root": ".", "task_file": "tasks.md", "artifact_dir": ".nightshift"},
            "safety": {"scoped_paths": ["."], "allowed_commands": [], "forbidden_commands": []},
            "agents": {
                "a": {"backend": "command", "command": "echo", "system_prompt": "a.md"},
                "b": {"backend": "command", "command": "echo", "system_prompt": "b.md"},
            },
            "pipeline": {
                "max_task_retries": 1,
                "stages": [
                    {
                        "id": "write",
                        "type": "file_writer",
                        "agent_pool": ["a", "b"],
                        "max_delete_ratio": 0.5,
                    }
                ],
            },
        }

        config = parse_config(raw, root / "nightshift.yaml")

        self.assertEqual(config.pipeline.stages[0].agent, "a")
        self.assertEqual(config.pipeline.stages[0].agent_pool, ("a", "b"))
        self.assertEqual(config.pipeline.stages[0].max_delete_ratio, 0.5)

    def test_patch_governor_rejects_deletion_heavy_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
            patch = "\n".join(
                [
                    "diff --git a/app.py b/app.py",
                    "--- a/app.py",
                    "+++ b/app.py",
                    "@@ -1,3 +1 @@",
                    "-one",
                    "-two",
                    "-three",
                    "+one",
                    "",
                ]
            )
            config = make_config(root, ())

            with self.assertRaises(Exception) as raised:
                validate_patch(patch, root, config.safety, max_delete_ratio=0.5)

            self.assertIn("deletion-heavy", str(raised.exception))

    def test_integration_run_creation_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            first = create_integration_run(root, template="basic")
            second = create_integration_run(root, template="basic")
            removed = cleanup_integration_runs(root / "integ_runs", keep=1)

            self.assertTrue(first.log_path.exists() or first.directory in removed)
            self.assertTrue(second.directory.exists())
            self.assertEqual(len(removed), 1)


if __name__ == "__main__":
    unittest.main()
