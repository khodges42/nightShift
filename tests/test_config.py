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
            self.assertEqual(config.pipeline.max_task_retries, 3)
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


if __name__ == "__main__":
    unittest.main()
