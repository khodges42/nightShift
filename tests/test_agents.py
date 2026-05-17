from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from nightshift.agents import AgentExecutor, build_prompt_bundle, parse_review_output
from nightshift.agents import AgentInvocation, format_agent_invocation
from nightshift.artifacts import ArtifactStore
from nightshift.config import AgentConfig, StageConfig
from nightshift.tasks import parse_tasks


TASK_MD = """# Tasks

- [ ] TASK-001: Add fake agent coverage

Description:
Exercise fake command agents.

Acceptance Criteria:
- Prompt includes task details
- Agent output is stored
"""


class AgentExecutorTests(unittest.TestCase):
    def test_build_prompt_bundle_includes_task_and_acceptance_criteria(self) -> None:
        task = parse_tasks(TASK_MD)[0]
        prompt = build_prompt_bundle(
            system_prompt="System rules",
            stage=StageConfig(id="plan", type="agent", agent="planner"),
            task=task,
            project_context="Project context",
            previous_outputs={"prior": "Earlier output"},
            retry_notes=["Retry note"],
        )

        self.assertIn("System rules", prompt)
        self.assertIn("TASK-001", prompt)
        self.assertIn("- Prompt includes task details", prompt)
        self.assertIn("Earlier output", prompt)
        self.assertIn("Retry note", prompt)

    def test_build_prompt_bundle_includes_task_context(self) -> None:
        task = parse_tasks(TASK_MD)[0]
        prompt = build_prompt_bundle(
            system_prompt="System rules",
            stage=StageConfig(id="plan", type="agent", agent="planner"),
            task=task,
            project_context="Project context",
            task_context="Task context body",
            previous_outputs={},
            retry_notes=[],
            retry_context="- No retries",
        )

        self.assertIn("## Task Context", prompt)
        self.assertIn("Task context body", prompt)
        self.assertIn("- No retries", prompt)

    def test_command_agent_writes_output_and_returns_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt_path = root / "planner.md"
            prompt_path.write_text("Plan carefully.", encoding="utf-8")
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            executor = AgentExecutor(
                root,
                {
                    "planner": AgentConfig(
                        id="planner",
                        backend="command",
                        command='python -c "import sys; print(sys.stdin.read())"',
                        system_prompt=Path("planner.md"),
                    )
                },
                artifacts,
            )
            task = parse_tasks(TASK_MD)[0]
            stage = StageConfig(id="plan", type="agent", agent="planner", output="plan.md")

            result = executor.run_stage(stage, task)

            self.assertEqual(result.status, "pass")
            output = (root / result.output_path).read_text(encoding="utf-8")
            self.assertIn("TASK-001", output)
            self.assertIn("Plan carefully.", output)

    def test_review_output_parser_accepts_structured_status(self) -> None:
        status, reason, next_stage, context_update = parse_review_output(
            "status: retry\nreason: Needs changes\nnext_stage: implement\ncontext_update: Fix tests\n"
        )

        self.assertEqual(status, "retry")
        self.assertEqual(reason, "Needs changes")
        self.assertEqual(next_stage, "implement")
        self.assertEqual(context_update, "Fix tests")

    def test_ollama_agent_invocation_uses_model_without_real_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt_path = root / "planner.md"
            prompt_path.write_text("Plan carefully.", encoding="utf-8")
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            executor = AgentExecutor(
                root,
                {
                    "planner": AgentConfig(
                        id="planner",
                        backend="ollama",
                        command=None,
                        model="tiny-model",
                        system_prompt=Path("planner.md"),
                    )
                },
                artifacts,
            )
            task = parse_tasks(TASK_MD)[0]
            stage = StageConfig(id="plan", type="agent", agent="planner", output="plan.md")

            completed = type(
                "Completed",
                (),
                {"returncode": 0, "stdout": "ollama output", "stderr": ""},
            )()
            with patch("nightshift.agents.subprocess.run", return_value=completed) as run:
                result = executor.run_stage(stage, task)

            self.assertEqual(result.status, "pass")
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], ["ollama", "run", "tiny-model"])
            output = (root / result.output_path).read_text(encoding="utf-8")
            self.assertIn("ollama run tiny-model", output)

    def test_openai_compatible_agent_sends_temperature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt_path = root / "planner.md"
            prompt_path.write_text("Plan carefully.", encoding="utf-8")
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            executor = AgentExecutor(
                root,
                {
                    "planner": AgentConfig(
                        id="planner",
                        backend="openai_compatible",
                        command=None,
                        model="tiny-model",
                        base_url="http://localhost:11434/v1",
                        temperature=0.2,
                        system_prompt=Path("planner.md"),
                    )
                },
                artifacts,
            )
            task = parse_tasks(TASK_MD)[0]
            stage = StageConfig(id="plan", type="agent", agent="planner", output="plan.md")
            response = MagicMock()
            response.__enter__.return_value.read.return_value = (
                b'{"choices":[{"message":{"content":"api output"}}]}'
            )

            with patch("nightshift.agents.request.urlopen", return_value=response) as urlopen:
                result = executor.run_stage(stage, task)

            self.assertEqual(result.status, "pass")
            request_obj = urlopen.call_args.args[0]
            body = request_obj.data.decode("utf-8")
            self.assertIn('"temperature": 0.2', body)
            self.assertIn("api output", (root / result.output_path).read_text(encoding="utf-8"))

    def test_agent_artifact_format_tolerates_missing_streams(self) -> None:
        invocation = AgentInvocation(
            agent_id="planner",
            command="ollama run model",
            prompt="prompt",
            exit_code=0,
            stdout=None,  # type: ignore[arg-type]
            stderr=None,  # type: ignore[arg-type]
            duration_seconds=0.1,
        )

        output = format_agent_invocation("plan", invocation)

        self.assertIn("Agent: `planner`", output)
        self.assertIn("## stderr", output)


if __name__ == "__main__":
    unittest.main()
