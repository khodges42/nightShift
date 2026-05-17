# NIGHTSHIFT_CODEX.md

You are Codex working on **NightShift**, a local-first AI coding pipeline runner in python.

This file is the implementation-driving context document. Treat it as the project brief, architectural guide, and task checklist.

---

# 0. Project Identity

## Name

**NightShift**

## Tagline

Auditable local-first AI coding pipelines.

## Core Thesis

NightShift is not an autonomous coding god.

NightShift is a deterministic pipeline runner that lets unreliable AI agents perform bounded coding work inside scoped, auditable, test-driven workflows.

The user should be able to run NightShift overnight and wake up to:

* a reviewable repository state
* task artifacts
* plans
* logs
* diffs
* test output
* review notes
* a final report

## Priority Order

Optimize in this order:

1. Cheapness
2. Correctness
3. Auditability
4. Speed

This means:

* Prefer local models first.
* Keep context compact.
* Avoid token waste.
* Make failure explicit.
* Always produce artifacts.
* Do not optimize for cleverness before trust.

---

# 1. Product Summary

NightShift runs long-running AI-assisted coding pipelines against a scoped project directory.

A user provides:

* a repository
* a markdown task file
* a declarative pipeline config
* agent definitions
* allowed test/static commands

NightShift processes one task at a time:

```text
select task
  -> plan
  -> review plan
  -> implement
  -> run tests
  -> run static checks
  -> review result
  -> retry or complete
  -> write summary
```

The output is not automatically shipped.

The output is a reviewable work package.

---

# 2. Non-Negotiable Design Constraints

## 2.1 Local-first

The first implementation should assume local execution.

Primary target backend:

* local command-driven agent execution

Future-compatible backends:

* Ollama
* Claude Code
* Codex CLI
* OpenAI API
* Anthropic API

Do not overbuild backend support in v1.

Build a clean interface first.

---

## 2.2 Scoped directory access

NightShift must only operate inside a configured project root.

It must not casually read/write arbitrary paths.

All path resolution should:

* normalize paths
* reject path traversal
* reject writes outside project root
* prefer relative paths in artifacts

---

## 2.3 One task at a time

v1 runs one task at a time.

No parallel task execution.

No DAG executor yet.

---

## 2.4 Declarative config first

Use YAML for v1.

Do not implement arbitrary Python config yet.

The config should be expressive enough for:

* agents
* stages
* commands
* retries
* artifact directory
* task file location
* scoped paths
* allowlisted commands

---

## 2.5 Auditable artifacts

Every run should create a durable artifact tree.

Artifacts are core product behavior, not debug leftovers.

---

# 3. Architecture

## 3.1 Conceptual Components

```text
NightShift CLI
  |
  v
Config Loader
  |
  v
Task Parser
  |
  v
Pipeline Runner
  |
  +--> Agent Executor
  |
  +--> Command Executor
  |
  +--> Artifact Store
  |
  +--> Context Manager
  |
  v
Run Summary
```

---

## 3.2 Suggested Module Layout

Use this layout unless the existing repo already strongly implies another structure.

```text
nightshift/
  __init__.py
  cli.py
  config.py
  tasks.py
  pipeline.py
  stages.py
  agents.py
  commands.py
  artifacts.py
  context.py
  safety.py
  reports.py
  errors.py

tests/
  test_config.py
  test_tasks.py
  test_pipeline.py
  test_safety.py
  test_artifacts.py

examples/
  pipeline.yaml
  tasks.md
  agents/
    planner.md
    implementer.md
    reviewer.md

NIGHTSHIFT_CODEX.md
README.md
```

If this project is implemented in Rust instead of Python, preserve the same conceptual boundaries.

---

# 4. Config Format

## 4.1 Example `nightshift.yaml`

```yaml
project:
  name: example-project
  root: .
  task_file: tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: false
  scoped_paths:
    - src/
    - tests/
  allowed_commands:
    - cargo test
    - cargo fmt --check
    - cargo clippy -- -D warnings
  forbidden_commands:
    - rm -rf
    - git push
    - curl | bash

agents:
  planner:
    backend: command
    command: echo
    system_prompt: examples/agents/planner.md

  implementer:
    backend: command
    command: echo
    system_prompt: examples/agents/implementer.md

  reviewer:
    backend: command
    command: echo
    system_prompt: examples/agents/reviewer.md

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
        - cargo test
      output: test-output.txt

    - id: static
      type: command
      commands:
        - cargo fmt --check
        - cargo clippy -- -D warnings
      output: static-output.txt

    - id: review
      type: agent_review
      agent: reviewer
      on_fail: implement
      output: review.md

    - id: summarize
      type: summarize
      output: final-notes.md
```

---

# 5. Task File Format

## 5.1 Input Task Format

Tasks are markdown checklist items with acceptance criteria.

Example:

```markdown
# Tasks

- [ ] TASK-001: Add YAML config loading

Description:
Implement config loading for NightShift.

Acceptance Criteria:
- Loads `nightshift.yaml`
- Validates required fields
- Returns typed config object
- Includes tests for valid and invalid config

- [ ] TASK-002: Add artifact directory creation

Description:
Create per-run and per-task artifact directories.

Acceptance Criteria:
- Creates `.nightshift/runs/<timestamp>/`
- Creates task-specific folder
- Writes task snapshot
- Includes tests
```

## 5.2 Parser Requirements

The parser should identify:

* task id
* task title
* completion state
* description
* acceptance criteria
* optional dependency notes

For v1, parsing can be simple and documented.

Do not try to support every markdown style.

---

# 6. Pipeline Model

## 6.1 State Machine, Not DAG

v1 should use a configurable state machine.

Reason:

* one task at a time
* retry loops matter
* easier to audit
* easier to debug
* easier MVP

A stage returns a `StageResult`.

Suggested shape:

```python
@dataclass
class StageResult:
    stage_id: str
    status: Literal["pass", "fail", "retry", "escalate"]
    reason: str
    output_path: str | None = None
    next_stage: str | None = None
    context_update: str | None = None
```

Equivalent Rust structs are fine if using Rust.

## 6.2 Retry Behavior

Retry behavior should be deterministic.

Rules:

* retries are counted per task
* max retries come from config
* failed review stages can redirect to configured `on_fail`
* after max retries, task is marked failed
* failure is summarized in artifacts

---

# 7. Agent Model

## 7.1 Agent Definition

Agents have:

* id
* backend
* command or model
* system prompt file
* role

For v1, support a `command` backend first.

This lets the user wrap:

* Codex
* Claude Code
* Ollama scripts
* local model scripts
* fake test agents

## 7.2 Agent Invocation

The runner should construct a prompt/input bundle containing:

* system prompt
* task markdown
* acceptance criteria
* relevant project context
* previous stage output
* retry notes, if any
* required output contract

The agent should write output to the configured artifact path.

Do not pass giant history blobs.

---

# 8. Context System

## 8.1 Context Layers

There are three context layers:

```text
project context
  long-lived, compact, shared across tasks

task context
  specific to the current task

retry context
  compact notes from failed attempts
```

## 8.2 Project Context

Stored at:

```text
.nightshift/project-context.md
```

Contains:

* architecture notes
* repo conventions
* summaries from completed tasks
* high-value durable facts

## 8.3 Task Context

Stored per task:

```text
.nightshift/runs/<run-id>/tasks/<task-id>/context.md
```

## 8.4 Context Compaction

After each task, write:

```text
context-out.md
```

Then selectively bubble useful durable information into project context.

Do not automatically dump everything into project context.

---

# 9. Artifact Layout

Every run should create:

```text
.nightshift/
  project-context.md
  runs/
    <run-id>/
      run-summary.md
      config.snapshot.yaml
      tasks/
        TASK-001/
          task.md
          plan.md
          plan-review.md
          implementation-log.md
          test-output.txt
          static-output.txt
          review.md
          final-notes.md
          diff.patch
          context.md
          context-out.md
```

Artifacts should be written even on failure.

---

# 10. Safety Rules

## 10.1 Path Safety

Implement helpers that:

* resolve paths against project root
* reject writes outside project root
* reject `..` traversal that escapes root
* prefer pathlib/path abstractions

## 10.2 Command Safety

For v1:

* only run commands listed in `allowed_commands`
* block commands containing known forbidden fragments
* record all command output
* record exit code
* set timeouts when practical

## 10.3 Git Safety

v1 should support config option:

```yaml
require_clean_worktree: true | false
```

If true, abort when git working tree is dirty.

Do not implement automatic branch creation in v1.

Do not push.

---

# 11. CLI Commands

Recommended initial CLI:

```bash
nightshift init
nightshift validate
nightshift run
nightshift run --task TASK-001
nightshift status
```

## 11.1 `nightshift init`

Creates example files:

* `nightshift.yaml`
* `tasks.md`
* `agents/planner.md`
* `agents/implementer.md`
* `agents/reviewer.md`

## 11.2 `nightshift validate`

Validates:

* config file exists
* task file exists
* scoped paths are inside root
* agents exist
* prompt files exist
* allowed commands are valid strings
* pipeline references valid agents

## 11.3 `nightshift run`

Runs the next incomplete task.

## 11.4 `nightshift run --task TASK-001`

Runs a specific task.

## 11.5 `nightshift status`

Prints:

* current config
* task count
* completed/incomplete tasks
* latest run directory

---

# 12. Testing Strategy

Write tests early.

Minimum tests:

* config loading happy path
* config missing required fields
* markdown task parsing
* artifact directory creation
* path traversal rejection
* command allowlist behavior
* forbidden command rejection
* simple pipeline execution with fake agents
* retry limit behavior

Use fake agents for tests.

Do not require real LLM calls in unit tests.

---

# 13. MVP Task Checklist

## Phase 1: Skeleton

* [ ] Create project package/module layout
* [ ] Add CLI entry point
* [ ] Add `nightshift init`
* [ ] Generate example `nightshift.yaml`
* [ ] Generate example `tasks.md`
* [ ] Generate example agent prompt files

Acceptance Criteria:

* User can run init command
* Expected files are created
* Existing files are not overwritten without confirmation or force flag

---

## Phase 2: Config Loading

* [ ] Implement YAML config loader
* [ ] Define typed config objects
* [ ] Validate required sections
* [ ] Validate agent references
* [ ] Validate pipeline stages
* [ ] Add tests

Acceptance Criteria:

* Valid config loads
* Invalid config fails with clear error
* Pipeline stages cannot reference missing agents

---

## Phase 3: Safety Layer

* [ ] Implement project root resolution
* [ ] Implement scoped path validation
* [ ] Implement safe artifact path creation
* [ ] Implement command allowlist check
* [ ] Implement forbidden command fragment check
* [ ] Add tests for path traversal
* [ ] Add tests for forbidden commands

Acceptance Criteria:

* Cannot write outside project root
* Cannot execute commands outside allowlist
* Dangerous command fragments are blocked

---

## Phase 4: Task Parser

* [ ] Parse markdown task checklist
* [ ] Extract task id
* [ ] Extract title
* [ ] Extract description
* [ ] Extract acceptance criteria
* [ ] Support selecting next incomplete task
* [ ] Support selecting specific task id
* [ ] Add tests

Acceptance Criteria:

* Parser handles documented task format
* Parser returns useful errors for malformed tasks
* Task selection works

---

## Phase 5: Artifact Store

* [ ] Create `.nightshift/`
* [ ] Create per-run directory
* [ ] Create per-task directory
* [ ] Write config snapshot
* [ ] Write task snapshot
* [ ] Write stage outputs
* [ ] Write command outputs
* [ ] Write final task notes
* [ ] Add tests

Acceptance Criteria:

* Every run creates deterministic artifact structure
* Artifacts are present even when stages fail

---

## Phase 6: Command Executor

* [ ] Implement command stage execution
* [ ] Capture stdout
* [ ] Capture stderr
* [ ] Capture exit code
* [ ] Persist command output
* [ ] Return structured stage result
* [ ] Add tests with harmless commands

Acceptance Criteria:

* Passing command returns pass
* Failing command returns fail
* Output is written to artifact file

---

## Phase 7: Agent Executor

* [ ] Implement `command` backend agent
* [ ] Load system prompt file
* [ ] Build prompt bundle
* [ ] Pass prompt to command backend
* [ ] Capture output
* [ ] Persist output
* [ ] Return structured stage result
* [ ] Add fake-agent tests

Acceptance Criteria:

* Fake command agent can produce stage output
* Prompt includes task and acceptance criteria
* Agent output is stored in artifacts

---

## Phase 8: Pipeline Runner

* [ ] Execute configured stages in order
* [ ] Stop on unrecoverable failure
* [ ] Support `on_fail` stage redirection
* [ ] Track retry count
* [ ] Enforce max task retries
* [ ] Write per-stage summaries
* [ ] Add tests

Acceptance Criteria:

* Happy path pipeline completes
* Failed review can retry implementation
* Retry limit is enforced
* Final task status is recorded

---

## Phase 9: Context Manager

* [ ] Create project context file if absent
* [ ] Create task context file
* [ ] Include project context in agent prompt bundle
* [ ] Include prior stage notes in retry prompt
* [ ] Write `context-out.md`
* [ ] Add tests

Acceptance Criteria:

* Context files are created
* Agent prompt receives compact context
* Context output is persisted

---

## Phase 10: Reports

* [ ] Generate task final report
* [ ] Generate run summary
* [ ] Include task status
* [ ] Include retry count
* [ ] Include modified files if available
* [ ] Include test/static results
* [ ] Include artifact paths
* [ ] Add tests

Acceptance Criteria:

* User can inspect one summary after run
* Summary explains what happened without reading every artifact

---

## Phase 11: README

* [ ] Explain what NightShift is
* [ ] Explain what it is not
* [ ] Add quickstart
* [ ] Add config example
* [ ] Add task file example
* [ ] Add safety model explanation
* [ ] Add MVP status

Acceptance Criteria:

* A new user can understand and run the MVP
* README emphasizes reviewable output, not blind autonomy

---

# 14. Implementation Guidance

## 14.1 Prefer boring code

This project should be reliable.

Do not make clever abstractions before the simple pipeline works.

## 14.2 Tests are part of the product

This is an AI automation safety tool.

Tests are credibility.

## 14.3 Make errors helpful

Bad:

```text
ValueError: invalid config
```

Good:

```text
Config error: pipeline stage 'review_plan' references unknown agent 'critic'.
Defined agents: planner, implementer, reviewer.
```

## 14.4 Do not assume real LLMs in tests

Use fake command agents.

Real model integration can come later.

## 14.5 Keep artifacts human-readable

Prefer markdown, YAML, and plain text.

---

# 15. Suggested Agent Prompt Files

## `agents/planner.md`

```markdown
You are the planning agent for NightShift.

Your job is to create a conservative implementation plan for one coding task.

Rules:
- Do not write code.
- Identify relevant files.
- Preserve existing behavior.
- Prefer small changes.
- Include test strategy.
- Include risks.

Output:
# Plan

## Summary

## Relevant Files

## Steps

## Test Strategy

## Risks

## Acceptance Criteria Mapping
```

## `agents/implementer.md`

```markdown
You are the implementation agent for NightShift.

Your job is to implement the approved plan inside the scoped project directory.

Rules:
- Make the smallest correct change.
- Do not edit files outside scope.
- Do not skip tests intentionally.
- Preserve existing style.
- Write useful implementation notes.

Output:
# Implementation Notes

## Changed Files

## Summary

## Tests Added or Updated

## Risks

## Follow-up Notes
```

## `agents/reviewer.md`

```markdown
You are the review agent for NightShift.

Your job is to decide whether the current task should pass, retry implementation, retry planning, or fail.

Priorities:
1. Correctness
2. Safety
3. Acceptance criteria
4. Maintainability
5. Minimality

Output exactly:

status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>
```

---

# 16. Definition of Done for MVP

NightShift MVP is done when:

* `nightshift init` creates a usable starter project
* `nightshift validate` catches bad config
* `nightshift run` can process one markdown task
* pipeline stages execute in order
* fake command agents work
* command stages run safely
* artifacts are written
* retry limits work
* final report is generated
* tests cover core safety and pipeline behavior

---

# 17. Future Features

Do not implement these until MVP is stable:

* DAG workflows
* parallel tasks
* Git branches per task
* remote workers
* cloud agent APIs
* dashboard UI
* prompt A/B testing
* model cost telemetry
* agent tournaments
* constraint-language experiments
* task dependency solver
* self-improving prompt library

---

# 18. Final Instruction to Codex

Build this incrementally.

Start with the smallest vertical slice:

```text
init -> validate -> parse one task -> create artifacts -> run fake pipeline -> write summary
```

Then add safety, retries, command execution, and real agent wrappers.

Do not build the cathedral before the generator turns on.

The goal is boring, auditable leverage.
