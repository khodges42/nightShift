from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nightshift.artifacts import ArtifactStore
from nightshift.runlog import RunLogger, format_status_event_message
from nightshift.terminal import (
    HOTDOG_ANIMATIONS,
    TerminalAnimation,
    animation_frames,
    format_banner,
    format_console_event_line,
    should_animate,
)


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

    def test_animation_frames_fall_back_to_agent_thinking(self) -> None:
        self.assertEqual(animation_frames("missing"), tuple(HOTDOG_ANIMATIONS["agent_thinking"]))
        self.assertEqual(animation_frames("classic_dance"), tuple(HOTDOG_ANIMATIONS["classic_dance"]))
        self.assertEqual(animation_frames("status_dots"), tuple(HOTDOG_ANIMATIONS["status_dots"]))

    def test_terminal_animation_is_disabled_for_non_tty(self) -> None:
        stream = StringIO()
        animation = TerminalAnimation(stream=stream)

        with animation:
            pass

        self.assertEqual(stream.getvalue(), "")

    def test_terminal_animation_renders_immediately_when_started(self) -> None:
        stream = FakeTTY()
        animation = TerminalAnimation(
            name="status_dots",
            message="Starting",
            stream=stream,
            interval_seconds=60,
        )

        animation.start()
        output = stream.getvalue()
        animation.stop()

        self.assertIn("[.  ] | Starting", output)

    def test_terminal_animation_does_not_depend_on_color_output(self) -> None:
        stream = FakeTTY()
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            self.assertTrue(should_animate(stream))

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

    def test_run_logger_status_callback_gets_compact_stage_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = ArtifactStore(root, ".nightshift", run_id="test-run")
            statuses: list[str] = []
            logger = RunLogger(status=statuses.append)
            logger.bind(artifacts)

            logger.event(
                "stage.start",
                "Starting stage",
                task_id="TASK-001",
                stage_id="implement",
                stage_type="file_writer",
                retry_count=2,
            )
            logger.event(
                "agent.start",
                "Starting agent",
                task_id="TASK-001",
                agent_id="implementer",
                model="qwen3-coder:30b",
            )

            self.assertEqual(statuses[0], "Task: TASK-001 | Stage: implement (file_writer) retry 2")
            self.assertEqual(statuses[1], "Task: TASK-001 | Agent: implementer | Model: qwen3-coder:30b")

    def test_format_status_event_message_reports_retries(self) -> None:
        message = format_status_event_message(
            "stage.retry",
            "Redirecting after stage result",
            {
                "task_id": "TASK-001",
                "stage_id": "test",
                "next_stage": "implement",
                "retry_count": 1,
            },
        )

        self.assertEqual(message, "Task: TASK-001 | Retrying after test -> implement retry 1")


if __name__ == "__main__":
    unittest.main()
