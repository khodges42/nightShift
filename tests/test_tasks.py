from pathlib import Path
import tempfile
import unittest

from nightshift.errors import TaskError
from nightshift.tasks import (
    parse_task_file,
    parse_tasks,
    select_next_incomplete_task,
    select_task_by_id,
)


TASKS_MD = """# Tasks

- [x] TASK-001: Completed task

Description:
Already done.

Acceptance Criteria:
- It is complete

- [ ] TASK-002: Add artifact directory creation

Description:
Create per-run and per-task artifact directories.

Dependencies:
- TASK-001

Acceptance Criteria:
- Creates `.nightshift/runs/<timestamp>/`
- Creates task-specific folder
- Writes task snapshot
"""


class TaskParserTests(unittest.TestCase):
    def test_parse_documented_task_format(self) -> None:
        tasks = parse_tasks(TASKS_MD)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[1].id, "TASK-002")
        self.assertEqual(tasks[1].title, "Add artifact directory creation")
        self.assertFalse(tasks[1].completed)
        self.assertEqual(
            tasks[1].description,
            "Create per-run and per-task artifact directories.",
        )
        self.assertEqual(tasks[1].dependencies, ("TASK-001",))
        self.assertEqual(len(tasks[1].acceptance_criteria), 3)
        self.assertIn("TASK-002", tasks[1].raw_markdown)

    def test_select_next_incomplete_task(self) -> None:
        tasks = parse_tasks(TASKS_MD)

        selected = select_next_incomplete_task(tasks)

        self.assertEqual(selected.id, "TASK-002")

    def test_select_task_by_id(self) -> None:
        tasks = parse_tasks(TASKS_MD)

        selected = select_task_by_id(tasks, "TASK-001")

        self.assertTrue(selected.completed)

    def test_select_task_by_id_reports_available_tasks(self) -> None:
        tasks = parse_tasks(TASKS_MD)

        with self.assertRaisesRegex(TaskError, "Available tasks: TASK-001, TASK-002"):
            select_task_by_id(tasks, "TASK-999")

    def test_parse_task_file_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaisesRegex(TaskError, "outside project root"):
                parse_task_file(root, "../tasks.md")

    def test_malformed_task_header_has_useful_error(self) -> None:
        markdown = """# Tasks

- [ ] Add YAML config loading

Acceptance Criteria:
- Loads config
"""

        with self.assertRaisesRegex(TaskError, "malformed task header"):
            parse_tasks(markdown)

    def test_missing_acceptance_criteria_fails(self) -> None:
        markdown = """# Tasks

- [ ] TASK-001: Missing criteria

Description:
No acceptance criteria.
"""

        with self.assertRaisesRegex(TaskError, "missing Acceptance Criteria"):
            parse_tasks(markdown)

    def test_no_tasks_fails(self) -> None:
        with self.assertRaisesRegex(TaskError, "no tasks found"):
            parse_tasks("# Tasks\n\nNothing here.\n")


if __name__ == "__main__":
    unittest.main()
