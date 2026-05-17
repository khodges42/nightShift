"""Built-in starter file templates for `nightshift init`."""

NIGHTSHIFT_YAML = """project:
  name: example-project
  root: .
  task_file: tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: false
  scoped_paths:
    - .
  allowed_commands:
    - python -m unittest
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
    command: echo
    system_prompt: agents/reviewer.md

pipeline:
  max_task_retries: 3
  stages:
    - id: plan
      type: agent
      agent: planner
      output: plan.md

    - id: review_plan
      type: agent_review
      agent: reviewer
      on_fail: plan
      output: plan-review.md

    - id: implement
      type: agent
      agent: implementer
      output: implementation-log.md

    - id: test
      type: command
      commands:
        - python -m unittest
      output: test-output.txt

    - id: review
      type: agent_review
      agent: reviewer
      on_fail: implement
      output: review.md

    - id: summarize
      type: summarize
      output: final-notes.md
"""

TASKS_MD = """# Tasks

- [ ] TASK-001: Add your first NightShift task

Description:
Describe the coding task NightShift should work on.

Acceptance Criteria:
- The expected behavior is clear
- The task can be reviewed from generated artifacts
"""

PLANNER_PROMPT = """# Planner

You are the planning agent for NightShift.

Create a conservative implementation plan for one coding task.

Rules:
- Do not write code.
- Identify relevant files.
- Preserve existing behavior.
- Prefer small changes.
- Include test strategy.
- Include risks.
"""

IMPLEMENTER_PROMPT = """# Implementer

You are the implementation agent for NightShift.

Implement the approved plan inside the scoped project directory.

Rules:
- Make the smallest correct change.
- Do not edit files outside scope.
- Preserve existing style.
- Write useful implementation notes.
"""

REVIEWER_PROMPT = """# Reviewer

You are the review agent for NightShift.

Decide whether the current task should pass, retry implementation, retry planning, or fail.

Output exactly:

status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>
"""
