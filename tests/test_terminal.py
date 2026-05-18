from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nightshift.artifacts import ArtifactStore
from nightshift.runlog import RunLogger
from nightshift.terminal import format_banner, format_console_event_line


class FakeTTY(StringIO):
    def isatty(self) -> bool:
        return True


class TerminalStylingTests(unittest.TestCase):
    def test_banner_is_plain_without_tty(self) -> None:
        banner = format_banner(stream=StringIO())
        self.assertIn("NightShift", banner)
        self.assertNotIn("\x1b[", banner)

    def test_banner_uses_ansi_when_tty(self) -> None:
        banner = format_banner(stream=FakeTTY())
        self.assertIn("NightShift", banner)
        self.assertIn("\x1b[", banner)

    def test_console_event_line_colors_success_and_failure(self) -> None:
        success = format_console_event_line(
            "2026-05-17T00:00:00Z",
            "task.finish",
            "Finished task",
            {"status": "complete"},
            stream=FakeTTY(),
        )
        failure = format_console_event_line(
            "2026-05-17T00:00:00Z",
            "task.finish",
            "Finished task",
            {"status": "failed"},
            stream=FakeTTY(),
        )
        self.assertIn("\x1b[32m", success)
        self.assertIn("\x1b[31m", failure)
        self.assertTrue(success.endswith("\x1b[0m"))
        self.assertTrue(failure.endswith("\x1b[0m"))

    def test_run_logger_console_output_is_separate_from_run_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            console_lines: list[str] = []
            logger = RunLogger(console=console_lines.append)
            logger.bind(artifacts)
            with patch(
                "nightshift.runlog.format_console_event_line",
                return_value="\x1b[32mstyled line\x1b[0m",
            ):
                logger.event("task.finish", "Finished task", status="complete", token="abc")

            self.assertEqual(console_lines[-1], "\x1b[32mstyled line\x1b[0m")
            run_log = artifacts.run_log_path.read_text(encoding="utf-8")
            self.assertIn("task.finish", run_log)
            self.assertIn("status=complete", run_log)
            self.assertNotIn("\x1b[", run_log)
            self.assertNotIn("abc", run_log)


if __name__ == "__main__":
    unittest.main()
