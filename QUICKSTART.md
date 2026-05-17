# NightShift Quickstart

This guide runs the current MVP with safe example files.

## 1. Install for Development

```bash
pip install -e .
```

Or run the module directly:

```bash
python -m nightshift.cli --help
```

## 2. Create Starter Files

From a project directory:

```bash
nightshift init
```

This creates:

```text
nightshift.yaml
tasks.md
agents/
```

Existing starter files are not overwritten unless you pass `--force`.

## 3. Validate

```bash
nightshift validate
```

Validation checks config structure, task parsing, prompt files, scoped paths, and command safety.

## 4. Run One Task

Run the next incomplete task:

```bash
nightshift run
```

Run a specific task:

```bash
nightshift run --task TASK-001
```

## 5. Review Artifacts

After a run, inspect:

```text
.nightshift/runs/<run-id>/
```

Useful files:

```text
run-summary.md
config.snapshot.yaml
tasks/TASK-001/task.md
tasks/TASK-001/context.md
tasks/TASK-001/plan.md
tasks/TASK-001/test-output.txt
tasks/TASK-001/stage-results.md
tasks/TASK-001/context-out.md
tasks/TASK-001/final-notes.md
```

## Example Templates

Example run files are available in `templates/`.
They are safe starter examples and use command-backed fake agents.

The repository also includes a complete sample target project:

```text
examples/quickstart-lisp/
```

Copy that directory elsewhere if you want to test NightShift against a multi-task project.

## Quickstart Test Project

A good first real target project is a tiny Lisp interpreter in Python. It is small enough to review, but it naturally breaks into multiple tasks that test NightShift's planning, implementation, command execution, artifacts, reports, and dependency handling.

If you do not want a language interpreter, use a small config parser or markdown todo CLI instead. The Lisp interpreter is the recommended default because it has clear incremental milestones and simple tests.

### 1. Create a Target Project

```bash
mkdir tiny-lisp
cd tiny-lisp
mkdir agents tests
touch lisp.py tests/test_lisp.py
```

### 2. Add `nightshift.yaml`

```yaml
project:
  name: tiny-lisp
  root: .
  task_file: tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: false
  scoped_paths:
    - .
  allowed_commands:
    - python -m unittest discover -v
  forbidden_commands:
    - rm -rf
    - git push
    - curl | bash

agents:
  planner:
    backend: command
    command: echo
    system_prompt: agents/planner.md

  implementer:
    backend: command
    command: echo
    system_prompt: agents/implementer.md

  reviewer:
    backend: command
    command: python -c "print('status: pass'); print('reason: quickstart reviewer accepted artifacts')"
    system_prompt: agents/reviewer.md

pipeline:
  max_task_retries: 1
  continue_on_task_failure: false
  stages:
    - id: plan
      type: agent
      agent: planner
      output: plan.md

    - id: implement
      type: agent
      agent: implementer
      output: implementation-log.md

    - id: test
      type: command
      commands:
        - python -m unittest discover -v
      output: test-output.txt

    - id: review
      type: agent_review
      agent: reviewer
      on_fail: implement
      output: review.md

    - id: summarize
      type: summarize
      output: final-notes.md
```

This uses fake command agents so the pipeline is safe and deterministic. Replace `command: echo` later with your real local agent wrapper.

### 3. Add `tasks.md`

```markdown
# Tasks

- [ ] TASK-001: Parse Lisp expressions

Description:
Implement tokenization and parsing for a tiny Lisp subset.

Acceptance Criteria:
- Parses numbers
- Parses symbols
- Parses nested lists
- Raises useful errors for unbalanced parentheses
- Includes unit tests

- [ ] TASK-002: Evaluate arithmetic forms

Dependencies:
- TASK-001

Description:
Evaluate parsed arithmetic expressions.

Acceptance Criteria:
- Supports `+`, `-`, `*`, and `/`
- Evaluates nested arithmetic
- Includes unit tests

- [ ] TASK-003: Add variables and definitions

Dependencies:
- TASK-002

Description:
Add an environment and support variable lookup and definitions.

Acceptance Criteria:
- Supports symbol lookup
- Supports `(define name value)`
- Keeps environment behavior tested

- [ ] TASK-004: Add conditionals

Dependencies:
- TASK-003

Description:
Implement simple truthiness and `if` expressions.

Acceptance Criteria:
- Supports `(if condition then else)`
- Handles false-like values consistently
- Includes tests for both branches
```

### 4. Add Prompt Files

`agents/planner.md`:

```markdown
You are the planning agent. Create a small, conservative plan for the task.
Do not write code. Include files to edit, tests to add, and risks.
```

`agents/implementer.md`:

```markdown
You are the implementation agent. Implement the smallest correct change.
Preserve existing behavior and include tests.
```

`agents/reviewer.md`:

```markdown
You are the review agent. Decide whether the task should pass, retry, or fail.

Output:
status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>
```

### 5. Add an Initial Passing Test File

```python
# tests/test_lisp.py
import unittest


class SmokeTests(unittest.TestCase):
    def test_smoke(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
```

### 6. Validate and Run

```bash
nightshift validate
nightshift status
nightshift run --task TASK-001
```

Run all currently runnable tasks:

```bash
nightshift run --all
```

Because the example uses fake agents, it will not actually implement the Lisp interpreter by itself. It is meant to verify the pipeline, dependency handling, reports, and artifacts before you connect a real command-backed agent.

### 7. Review Artifacts

After a run, inspect:

```text
.nightshift/runs/<run-id>/run-summary.md
.nightshift/runs/<run-id>/tasks/TASK-001/plan.md
.nightshift/runs/<run-id>/tasks/TASK-001/implementation-log.md
.nightshift/runs/<run-id>/tasks/TASK-001/test-output.txt
.nightshift/runs/<run-id>/tasks/TASK-001/review.md
.nightshift/runs/<run-id>/tasks/TASK-001/final-notes.md
```

The useful signal is whether NightShift selected the right task, respected dependencies, ran the command stage, wrote artifacts, updated task completion, and produced a clear summary.
