from pathlib import Path
from dataclasses import replace
import tempfile
import unittest

from nightshift.artifacts import ArtifactStore
from nightshift.config import parse_config, StageConfig
from nightshift.dependencies import diagnose_python_dependencies
from nightshift.escalation import evaluate_retry_churn
from nightshift.failures import build_failure_signature, classify_failure
from nightshift.integ import cleanup_integration_runs, create_integration_run
from nightshift.patches import validate_patch
from nightshift.pipeline import PipelineRunner
from nightshift.retry_memory import RetryMemoryEntry
from nightshift.tasks import parse_tasks

from tests.test_pipeline import TASK_MD, make_config, _write_common_files


class ReliabilityFeatureTests(unittest.TestCase):
    def test_failure_classifier_detects_missing_dependency(self) -> None:
        result = classify_failure("ModuleNotFoundError: No module named 'flask'", exit_code=1)

        self.assertEqual(result.category, "missing dependency")
        self.assertIn("flask", result.probable_root_cause)
        self.assertIn("do not retry", result.retry_recommendation)

    def test_failure_classifier_prioritizes_module_not_found_in_pytest_import_error(self) -> None:
        result = classify_failure(
            "\n".join(
                [
                    "ImportError while importing test module 'tests/test_app.py'.",
                    "ModuleNotFoundError: No module named 'deaddrop_app'",
                ]
            ),
            exit_code=2,
        )

        self.assertEqual(result.category, "missing dependency")
        self.assertIn("deaddrop_app", result.probable_root_cause)

    def test_failure_classifier_detects_local_import_mismatch(self) -> None:
        result = classify_failure(
            "\n".join(
                [
                    "ImportError while importing test module 'tests/test_snippets.py'.",
                    "tests/test_snippets.py:2: in <module>",
                    "    from app import app, session, Snippet",
                    "E   ModuleNotFoundError: No module named 'app'",
                ]
            ),
            exit_code=2,
        )

        self.assertEqual(result.category, "local import mismatch")
        self.assertIn("project package layout", result.probable_root_cause)

    def test_dependency_diagnostic_does_not_treat_local_imports_as_packages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

            result = diagnose_python_dependencies(root, "ModuleNotFoundError: No module named 'models'")

            self.assertEqual(result.missing_imports, ("models",))
            self.assertIn("local module import mistakes", result.recommendation)

    def test_failure_classifier_detects_no_tests_ran(self) -> None:
        result = classify_failure("no tests ran in 0.19s", exit_code=5)

        self.assertEqual(result.category, "test expectation mismatch")
        self.assertIn("did not collect any tests", result.probable_root_cause)

    def test_failure_classifier_treats_traceback_into_source_as_logic_bug(self) -> None:
        result = classify_failure(
            "\n".join(
                [
                    '  File "C:\\repo\\project\\src\\deaddrop_app\\app.py", line 31, in get_db',
                    "    if 'db' not in g:",
                    "NameError: name 'g' is not defined",
                ]
            ),
            exit_code=1,
        )

        self.assertEqual(result.category, "logic bug")
        self.assertIn("src\\deaddrop_app\\app.py", result.probable_root_cause)

    def test_retry_churn_stops_on_repeated_failure_signature(self) -> None:
        entries = (
            RetryMemoryEntry(
                attempt=1,
                stage_id="test",
                status="fail",
                cause="Command exited with code 1: python -m pytest -q",
                next_stage="implement",
                failure_signature="NameError | src/deaddrop_app/app.py | 31 | python -m pytest -q",
            ),
            RetryMemoryEntry(
                attempt=2,
                stage_id="test",
                status="fail",
                cause="Command exited with code 1: python -m pytest -q",
                next_stage="implement",
                failure_signature="NameError | src/deaddrop_app/app.py | 31 | python -m pytest -q",
            ),
        )

        decision = evaluate_retry_churn(entries, retry_budget=4, repeated_signature_after=2)

        self.assertTrue(decision.should_stop)
        self.assertIn("same failure signature", decision.reason)

    def test_retry_churn_honors_configured_repeated_failure_threshold(self) -> None:
        entries = tuple(
            RetryMemoryEntry(
                attempt=attempt,
                stage_id="test",
                status="fail",
                cause="Command exited with code 1: python -m pytest -q",
                next_stage="implement",
                failure_signature="NameError | src/deaddrop_app/app.py | 31 | python -m pytest -q",
            )
            for attempt in range(1, 4)
        )

        decision = evaluate_retry_churn(entries, retry_budget=7, repeated_signature_after=6)

        self.assertFalse(decision.should_stop)

    def test_build_failure_signature_prefers_project_traceback_over_pytest_cache(self) -> None:
        signature = build_failure_signature(
            "\n".join(
                [
                    '  File "C:\\repo\\project\\src\\deaddrop_app\\app.py", line 31, in get_db',
                    "NameError: name 'g' is not defined",
                    '  File "C:\\Users\\metis\\...\\site-packages\\_pytest\\cacheprovider.py", line 429, in set',
                ]
            ),
            reason="Command exited with code 1: python -m pytest -q",
        )

        self.assertIn("src\\deaddrop_app\\app.py", signature)
        self.assertNotIn("_pytest\\cacheprovider.py", signature)

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
