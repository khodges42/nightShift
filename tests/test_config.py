from pathlib import Path
import tempfile
import unittest

from nightshift.config import load_config, validate_config
from nightshift.errors import ConfigError
from nightshift.init import init_project


class ConfigTests(unittest.TestCase):
    def test_valid_config_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)

            config = validate_config(root / "nightshift.yaml")

            self.assertEqual(config.project.name, "example-project")
            self.assertIn("planner", config.agents)
            self.assertEqual(config.pipeline.max_task_retries, 6)
            self.assertEqual(config.pipeline.stages[0].id, "plan")

    def test_missing_required_section_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "nightshift.yaml"
            config_path.write_text("project:\n  name: broken\n", encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "missing required section 'safety'"):
                load_config(config_path)

    def test_pipeline_stage_cannot_reference_missing_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_text = config_path.read_text(encoding="utf-8").replace(
                "agent: planner", "agent: critic", 1
            )
            config_path.write_text(config_text, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "references unknown agent 'critic'"):
                load_config(config_path)

    def test_on_fail_must_reference_existing_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_text = config_path.read_text(encoding="utf-8").replace(
                "on_fail: plan", "on_fail: missing_stage", 1
            )
            config_path.write_text(config_text, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "on_fail references unknown stage"):
                load_config(config_path)

    def test_validate_requires_prompt_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            (root / "agents" / "planner.md").unlink()

            with self.assertRaisesRegex(ConfigError, "system prompt does not exist"):
                validate_config(root / "nightshift.yaml")

    def test_validate_rejects_unallowlisted_stage_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_text = config_path.read_text(encoding="utf-8").replace(
                "- python -m unittest",
                "- python -m pytest",
                1,
            )
            config_path.write_text(config_text, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "not allowlisted"):
                validate_config(config_path)

    def test_max_task_retries_must_be_integer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "max_task_retries: 6",
                    "max_task_retries: three",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "pipeline.max_task_retries"):
                load_config(config_path)

    def test_require_clean_worktree_must_be_boolean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "require_clean_worktree: false",
                    "require_clean_worktree: no-thanks",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "safety.require_clean_worktree"):
                load_config(config_path)

    def test_command_backend_agent_requires_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "    command: echo\n    system_prompt: agents/planner.md",
                    "    system_prompt: agents/planner.md",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "must define command"):
                load_config(config_path)

    def test_ollama_backend_requires_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "backend: command\n    command: echo",
                    "backend: ollama",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "must define model"):
                load_config(config_path)

    def test_ollama_backend_and_experiment_metadata_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            text = config_path.read_text(encoding="utf-8").replace(
                "backend: command\n    command: echo",
                "backend: ollama\n    model: qwen2.5-coder:14b",
                1,
            )
            text = text.replace(
                "agents:",
                "experiment:\n  label: local-test\n  prompt_variant: v1\n\nagents:",
            )
            config_path.write_text(text, encoding="utf-8")

            config = load_config(config_path)

            self.assertEqual(config.agents["planner"].backend, "ollama")
            self.assertEqual(config.agents["planner"].model, "qwen2.5-coder:14b")
            self.assertEqual(config.experiment.label, "local-test")

    def test_openai_compatible_backend_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            text = config_path.read_text(encoding="utf-8").replace(
                "backend: command\n    command: echo",
                "backend: openai_compatible\n    model: local-model\n    base_url: http://localhost:11434/v1\n    temperature: 0.1",
                1,
            )
            config_path.write_text(text, encoding="utf-8")

            config = load_config(config_path)

            self.assertEqual(config.agents["planner"].backend, "openai_compatible")
            self.assertEqual(config.agents["planner"].base_url, "http://localhost:11434/v1")
            self.assertEqual(config.agents["planner"].temperature, 0.1)

    def test_command_stage_options_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "      output: test-output.txt",
                    "      output: test-output.txt\n      shell: false\n      timeout_seconds: 30\n      working_dir: .",
                    1,
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)
            test_stage = next(stage for stage in config.pipeline.stages if stage.id == "test")

            self.assertFalse(test_stage.shell)
            self.assertEqual(test_stage.timeout_seconds, 30)
            self.assertEqual(test_stage.working_dir, Path("."))

    def test_patch_validator_stage_options_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "    - id: summarize",
                    "    - id: validate_patch\n      type: patch_validator\n      max_files: 2\n      max_lines: 100\n      allowed_paths:\n        - tests\n      forbidden_paths:\n        - secrets\n\n    - id: summarize",
                    1,
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)
            patch_stage = next(stage for stage in config.pipeline.stages if stage.id == "validate_patch")

            self.assertEqual(patch_stage.max_files, 2)
            self.assertEqual(patch_stage.max_lines, 100)
            self.assertEqual(patch_stage.allowed_paths, ("tests",))
            self.assertEqual(patch_stage.forbidden_paths, ("secrets",))

    def test_file_writer_stage_requires_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            text = config_path.read_text(encoding="utf-8")
            config_path.write_text(
                text.replace(
                    "    - id: plan\n      type: agent\n      agent: planner\n      output: plan.md",
                    "    - id: write\n      type: file_writer",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "file_writer stage 'write' must reference an agent"):
                load_config(config_path)

    def test_patch_apply_mode_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "    - id: summarize",
                    "    - id: apply_patch\n      type: patch_apply\n      mode: dry_run\n\n    - id: summarize",
                    1,
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)
            apply_stage = next(stage for stage in config.pipeline.stages if stage.id == "apply_patch")

            self.assertEqual(apply_stage.mode, "dry_run")

    def test_agent_temperature_loads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "    system_prompt: agents/planner.md",
                    "    system_prompt: agents/planner.md\n    temperature: 0.2",
                    1,
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.agents["planner"].temperature, 0.2)

    def test_agent_ollama_options_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "    system_prompt: agents/planner.md",
                    "    system_prompt: agents/planner.md\n    num_ctx: 8192\n    num_predict: 4096\n    seed: 1\n    stop:\n      - STOP",
                    1,
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.agents["planner"].num_ctx, 8192)
            self.assertEqual(config.agents["planner"].num_predict, 4096)
            self.assertEqual(config.agents["planner"].seed, 1)
            self.assertEqual(config.agents["planner"].stop, ("STOP",))

    def test_agent_temperature_must_be_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "    system_prompt: agents/planner.md",
                    "    system_prompt: agents/planner.md\n    temperature: low",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "temperature"):
                load_config(config_path)

    def test_non_command_stage_cannot_define_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root)
            config_path = root / "nightshift.yaml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "      output: plan.md",
                    "      output: plan.md\n      commands:\n        - python -m unittest",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "non-command stage 'plan'"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
