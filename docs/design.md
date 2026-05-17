# NightShift

## Auditable Local-First AI Coding Pipelines

Version: v0.1 Draft
Author: K455
Status: Design Proposal

---

# 1. Executive Summary

NightShift is a local-first AI pipeline runner designed to execute long-running coding workflows against a constrained project workspace.

The system is intended to run overnight or unattended for extended periods while remaining:

* Cheap
* Correct
* Auditable
* Safe
* Reviewable

NightShift is not designed to be a fully autonomous "AI software engineer."
Instead, it is a deterministic orchestration system that allows fallible AI agents to operate within constrained, test-driven, auditable workflows.

The core philosophy is:

> Treat LLMs like unreliable distributed systems.

Agents are bounded by:

* Scoped repository access
* Structured stage contracts
* Explicit retry behavior
* Tests and static checks
* Review stages
* Context compaction
* Artifact logging

The intended workflow is:

1. User provides:

   * Repository
   * Task list
   * Pipeline configuration
   * Agent definitions

2. NightShift:

   * Selects the next task
   * Generates a plan
   * Reviews the plan
   * Implements changes
   * Runs tests/static analysis
   * Reviews results
   * Retries if necessary
   * Produces an overnight report

The result is a reviewable repository state and a full audit trail of AI behavior.

---

# 2. Goals

## 2.1 Primary Goals

### Local-first execution

The system should work primarily with local models and local execution environments.

Examples:

* Ollama
* Local transformers
* Local agent runtimes
* Claude Code
* Codex CLI

### Long-running unattended workflows

NightShift should support:

* Overnight execution
* Large task chains
* Multi-stage workflows
* Automated retries
* Context handoff between stages

### Auditability

Every important action should be recorded.

Users should be able to inspect:

* Prompts
* Plans
* Reviews
* Command outputs
* Diffs
* Test results
* Retry reasoning
* Final summaries

### Cheapness-first execution

The orchestration layer should assume:

* Cheap local models handle most work
* Expensive models are escalation layers
* Context size matters
* Token usage matters
* Retry cost matters

### Safe repository boundaries

The system should:

* Restrict file access
* Restrict shell commands
* Avoid destructive operations
* Minimize repository damage

---

## 2.2 Non-Goals (v1)

The following are intentionally out of scope for v1:

* Fully autonomous software development
* Parallel distributed execution
* Automatic deployment
* Cloud-native orchestration
* Dynamic self-modifying pipelines
* Autonomous internet access
* Agent swarms
* Arbitrary Python execution hooks
* Automatic git pushes
* Full DAG orchestration

---

# 3. Design Philosophy

NightShift is built around several core principles.

## 3.1 Deterministic orchestration

Agents are nondeterministic.

The orchestration system should not be.

Pipeline behavior should be:

* Predictable
* Reproducible
* Configurable
* Explicit

---

## 3.2 Structured state transitions

NightShift uses a state-machine workflow model.

A task moves through defined stages:

```text
Task Queue
  -> Plan
  -> Plan Review
  -> Implement
  -> Test
  -> Static Check
  -> Review
  -> Retry / Complete
```

Each stage produces:

```yaml
status: pass | fail | retry | escalate
reason: string
next_stage: optional
context_update: optional
```

This allows the pipeline runner to remain deterministic even while agents are probabilistic.

---

## 3.3 Context compaction

Agents should not inherit unlimited history.

Instead:

* Project-level context is persistent and compact
* Task-level context is scoped
* Retry context is summarized
* Stage context is minimized

This reduces:

* Token costs
* Context poisoning
* Hallucination drift
* Recursive confusion

---

## 3.4 Reviewability over autonomy

NightShift is optimized to produce:

* Reviewable code
* Reviewable reports
* Reviewable reasoning

The primary output is:

> A useful morning review state.

Not:

> Fully autonomous shipping.

---

# 4. Architecture Overview

## 4.1 High-Level Components

```text
+-------------------+
|   Task Parser     |
+-------------------+
          |
          v
+-------------------+
| Pipeline Runner   |
+-------------------+
          |
          v
+-------------------+
| Stage Executor    |
+-------------------+
     |        |
     |        +----------------+
     |                         |
     v                         v
+-----------+         +----------------+
| Agent API |         | Command Runner |
+-----------+         +----------------+
     |                         |
     v                         v
+-----------+         +----------------+
| LLM Model |         | Test/Lint/etc  |
+-----------+         +----------------+
```

---

## 4.2 Core Components

### Task Parser

Responsible for:

* Reading markdown task files
* Parsing acceptance criteria
* Tracking completion state
* Determining dependencies

---

### Pipeline Runner

Responsible for:

* Stage orchestration
* Retry logic
* State transitions
* Artifact management
* Context propagation

---

### Stage Executor

Responsible for:

* Executing stage definitions
* Calling agents
* Running commands
* Collecting outputs

---

### Agent Layer

Responsible for:

* Prompt construction
* Model backend integration
* Structured output parsing
* Context injection

---

### Command Runner

Responsible for:

* Executing tests
* Static analysis
* Formatting
* Shell command restrictions
* Sandboxing

---

# 5. Workflow Model

## 5.1 State Machine Model

NightShift uses a configurable state-machine workflow.

This was selected over:

* DAG orchestration
* Arbitrary scripting

because:

* v1 executes one task at a time
* Retry loops are first-class
* Auditability is easier
* Deterministic transitions are simpler

---

## 5.2 Default Pipeline

```text
PLAN
  ↓
REVIEW_PLAN
  ↓
IMPLEMENT
  ↓
TEST
  ↓
STATIC_ANALYSIS
  ↓
REVIEW
  ↓
DECISION
```

Decision outcomes:

* COMPLETE
* RETRY_IMPLEMENTATION
* RETRY_PLANNING
* FAIL

---

## 5.3 Configurable Pipelines

Pipelines are defined declaratively.

Users may:

* Swap stage orders
* Add/remove stages
* Define retry behavior
* Use different models
* A/B test prompts
* Experiment with reasoning structures

---

# 6. Configuration System

## 6.1 Configuration Format

NightShift uses YAML configuration files.

Reasons:

* Human-readable
* Good nested structure support
* Easier workflow representation than TOML
* Safer than arbitrary Python execution

---

## 6.2 Example Configuration

```yaml
project:
  name: my-project
  root: .
  task_file: tasks.md
  artifact_dir: .nightshift

safety:
  require_clean_worktree: true

  scoped_paths:
    - src/
    - tests/

  forbidden_commands:
    - rm -rf
    - git push

  allowed_commands:
    - cargo test
    - cargo fmt
    - cargo clippy

agents:
  planner:
    backend: ollama
    model: qwen2.5-coder:14b
    system_prompt: agents/planner.md

  implementer:
    backend: claude-code
    model: sonnet
    system_prompt: agents/implementer.md

  reviewer:
    backend: ollama
    model: deepseek-r1:32b
    system_prompt: agents/reviewer.md

pipeline:
  max_task_retries: 3

  stages:
    - id: plan
      type: agent
      agent: planner

    - id: review_plan
      type: review
      agent: reviewer
      on_fail: plan

    - id: implement
      type: agent
      agent: implementer

    - id: test
      type: command
      commands:
        - cargo test

    - id: static
      type: command
      commands:
        - cargo fmt --check
        - cargo clippy -- -D warnings

    - id: review
      type: review
      agent: reviewer
      on_fail: implement
```

---

# 7. Task System

## 7.1 Task Format

Tasks are defined in markdown.

Example:

```markdown
- [ ] TASK-001: Add retry support to pipeline runner

Acceptance Criteria:
- Retries configurable per stage
- Retry summaries persisted
- Retry count visible in final report
```

---

## 7.2 Task Lifecycle

Each task:

1. Is parsed
2. Is assigned a workspace
3. Receives planning
4. Receives implementation
5. Is validated
6. Is reviewed
7. Produces artifacts
8. Is marked complete or failed

---

## 7.3 Task Dependencies

Future versions may support:

```text
TASK-003 depends on TASK-001
```

However:

* Tasks should remain independently testable when possible
* Pipelines should maintain a buildable repository state

---

# 8. Agent Model

## 8.1 Agent Roles

Agents are specialized.

Example roles:

* planner
* implementer
* reviewer
* summarizer
* test-writer

---

## 8.2 Agent Definitions

Agents are configurable.

Each agent defines:

* Backend
* Model
* System prompt
* Constraints
* Output schema

---

## 8.3 Multi-Backend Support

NightShift should support:

* Ollama
* Claude Code
* Codex CLI
* Future local runners

This allows:

* Cheap local planning
* Expensive selective escalation
* Hybrid pipelines

---

## 8.4 Structured Outputs

Agents should emit machine-readable results.

Example:

```yaml
status: pass
summary: |
  Tests succeeded.
issues:
  - None
next_stage: review
```

---

# 9. Context System

## 9.1 Context Layers

NightShift uses layered context.

### Project Context

Long-lived information:

* Architecture
* Coding standards
* Constraints
* Previous summaries

---

### Task Context

Task-specific information:

* Acceptance criteria
* Relevant files
* Prior retries
* Implementation notes

---

### Retry Context

Compact summaries of:

* Previous failures
* Previous reviews
* Previous test errors

---

## 9.2 Context Compaction

Every stage should summarize output.

This prevents:

* Infinite context growth
* Token explosion
* Recursive hallucination
* Low-signal history accumulation

---

# 10. Safety Model

## 10.1 Repository Scope Restrictions

NightShift should restrict:

* Accessible directories
* Writable paths
* Executable commands

---

## 10.2 Command Restrictions

Commands are allowlisted.

Potentially dangerous commands are forbidden.

Examples:

```text
Forbidden:
- rm -rf
- git push
- curl | bash
```

---

## 10.3 Clean Worktree Requirement

v1 may optionally require:

```text
git status == clean
```

before execution.

This simplifies:

* Auditability
* Recovery
* Diff inspection

---

# 11. Testing and Validation

## 11.1 Validation Pipeline

Validation occurs in multiple stages:

```text
Tests
  ↓
Static Analysis
  ↓
Review Agent
  ↓
Decision
```

---

## 11.2 Global Test Suite

Tests are global.

Rationale:

* New changes must not break old functionality
* Pipeline should maintain cumulative stability

---

## 11.3 Generated Tests

Agents may generate tests for features.

Generated tests become part of the persistent suite.

---

# 12. Artifact System

## 12.1 Artifact Goals

Artifacts provide:

* Auditability
* Replayability
* Debugging
* Historical inspection
* Prompt experimentation

---

## 12.2 Example Layout

```text
.nightshift/
  project-context.md

  runs/
    2026-05-16-overnight/
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
          context-out.md
```

---

# 13. Overnight Report

At completion NightShift generates:

* Completed tasks
* Failed tasks
* Retry counts
* Files modified
* Test results
* Reviewer summaries
* Remaining issues
* Suggested follow-up work

The goal is:

> Wake up to a review package.

---

# 14. Future Directions

Potential future features:

* Parallel task execution
* DAG workflows
* Distributed workers
* Sandboxed containers
* Git branch isolation
* Agent tournaments
* Constraint language experimentation
* Prompt A/B testing
* Semantic memory systems
* Multi-repo orchestration
* Web dashboard
* Cost telemetry
* Human approval gates

---

# 15. Risks

## 15.1 Context poisoning

Mitigation:

* Context compaction
* Retry summarization
* Structured stage boundaries

---

## 15.2 Agent loops

Mitigation:

* Explicit retry counts
* Deterministic transitions
* Timeout handling

---

## 15.3 Repository damage

Mitigation:

* Scoped directories
* Command restrictions
* Validation stages

---

## 15.4 Cost explosion

Mitigation:

* Local-first execution
* Context minimization
* Escalation-only expensive models

---

# 16. Implemented Baseline

The MVP and post-MVP phases through phase 22 are implemented.

NightShift currently provides:

* `nightshift init` for starter project generation
* `nightshift validate` for config, prompt, task, dependency, path, and command validation
* `nightshift status` for read-only project inspection
* `nightshift run` for the next runnable incomplete task
* `nightshift run --task TASK-ID` for a specific task
* `nightshift run --all` for sequential multi-task execution
* `nightshift web` for a read-only artifact dashboard
* Markdown task parsing with descriptions, acceptance criteria, completion state, and dependency bullets
* Dependency validation for missing references and simple cycles
* Dependency-aware task selection and task blocking
* Declarative YAML pipeline execution
* Command, agent, agent-review, review, and summarize stage handling
* Retry redirection with a configured task retry limit
* Command-backed agents
* Ollama-backed local model agents
* Prompt bundle construction with project, task, retry, and previous-stage context
* Prompt snapshots and run metadata for experiment comparison
* Optional experiment labels and prompt variant metadata
* Command allowlists and forbidden-fragment checks
* Optional shell-free command execution
* Per-stage command timeouts
* Project-root-restricted command working directories
* Environment variable allowlists for command stages
* Scoped path and artifact path safety checks
* Optional clean-worktree enforcement
* Pre-run and post-run git status artifacts
* Per-task `diff.patch` artifacts
* Task completion mutation for successful runs
* Per-run and per-task markdown/text artifacts
* Project, task, retry, and context-out files
* Final task notes, stage summaries, task completion artifacts, and run summaries
* Documentation for config, artifact review, troubleshooting, and quickstart workflows
* A complete fake-agent quickstart Lisp example under `examples/quickstart-lisp/`

The system remains sequential and local-first. It is designed to produce reviewable artifacts and repository state, not to deploy, push, or autonomously ship changes.

---

# 17. Current Product Shape

The implemented product is now a practical local runner rather than only a single-task MVP.

## 17.1 CLI Workflow

Common workflow:

```text
nightshift init
nightshift validate
nightshift status
nightshift run
nightshift run --task TASK-001
nightshift run --all
nightshift web
```

The CLI can validate a project, select runnable tasks, enforce dependencies, run one or more tasks, and report artifact locations.

## 17.2 Artifact Workflow

Artifacts are still the primary audit surface.

Current run artifacts include:

```text
.nightshift/
  project-context.md
  runs/
    <run-id>/
      run-summary.md
      config.snapshot.yaml
      run-metadata.md
      prompts/
        <agent-id>.md
      tasks/
        TASK-001/
          task.md
          context.md
          plan.md
          implementation-log.md
          test-output.txt
          review.md
          stage-results.md
          context-out.md
          task-completion.md
          git-status-before.txt
          git-status-after.txt
          diff.patch
          final-notes.md
```

Exact task artifact names depend on configured stage `output` values.

## 17.3 Dashboard Workflow

The web dashboard is read-only and artifact-driven.

It currently:

* Lists runs from `.nightshift/runs/`
* Shows run summaries
* Links to text and markdown artifacts
* Safely rejects artifact path traversal
* Auto-refreshes

It does not:

* Start or stop runs
* Mutate config or tasks
* Provide approval gates
* Stream live process output
* Authenticate users

## 17.4 Known Limitations

Current limitations:

* Execution is sequential; there is no parallel task runner.
* The web dashboard is read-only and artifact-oriented.
* Live run progress is limited to basic CLI prints and artifact inspection.
* Flask is optional; `nightshift web` requires it to be installed.
* Ollama support depends on the user's local Ollama installation and model availability.
* Git artifacts can be unavailable or degraded in non-git repositories or repositories blocked by Git safe-directory rules.
* Task mutation is intentionally minimal and only flips matching checklist lines.
* Command configuration is safer than the MVP but is still string-first for compatibility.
* There is no branch isolation, resumable run state machine, approval workflow, or deployment integration.

---

# 18. Next Major Update Plan

The next major update should improve operational visibility while preserving the current artifact-first model.

## Phase 23: Improved Logging and Live Visibility

NightShift should make active runs easier to observe from both the CLI and the web dashboard.

Implementation tasks:

* [x] Add a small logging module with structured operational events.
* [x] Stream human-readable progress to the CLI during `run` and `run --all`.
* [x] Include run id, task id, stage id, agent/backend, command index, retry count, status, duration, and artifact path where available.
* [x] Write a per-run log file such as `.nightshift/runs/<run-id>/run.log`.
* [x] Optionally write or rotate an aggregate `.nightshift/nightshift.log` for cross-run troubleshooting.
* [x] Keep logs operational; do not duplicate full prompts, full model responses, or full command output that already lives in artifacts.
* [x] Redact or avoid secrets from logged environment/config values.
* [x] Add dashboard support for viewing the latest log tail.
* [x] Cap the dashboard log view to the last 100 lines by default.
* [x] Keep the full per-run log file available as an artifact unless a later size cap is configured.
* [x] Auto-refresh the dashboard log view with the existing dashboard refresh model.
* [x] Add tests for log writing, CLI progress hooks, dashboard log rendering, missing log files, and the 100-line cap.

Acceptance Criteria:

* A user running NightShift from a terminal can tell which task and stage are active.
* Long Ollama or command stages show enough lifecycle information that the process does not appear hung.
* The latest run log is visible from `nightshift web`.
* The web client displays at most the last 100 log lines by default.
* Logs point users to detailed artifacts instead of replacing them.
* Missing or partial log files do not crash the dashboard.

Notes:

* This phase should not add process control, websockets, authentication, or write actions to the web client.
* If future live streaming is needed, the first version can still use file tailing plus refresh before introducing websockets.
* Operational logs should complement artifacts: artifacts remain the source of detailed prompts, responses, command output, diffs, and summaries.

## Phase 24: Per-Agent Model Parameters

- [x] Add `temperature` to agent config.
- [x] Pass temperature to Ollama/OpenAI-compatible backends.
- [x] Default safely if omitted.
- [x] Add config validation tests.

## Phase 25: Repo Lookup Tools MVP

- [x] Add tool interface for repo operations.
- [x] Implement scoped `list_files`.
- [x] Implement scoped `read_file`.
- [x] Implement scoped `grep`.
- [x] Enforce existing path safety rules.
- [x] Log tool calls as artifacts.

## Phase 26: Planner Code-Discovery Support

- [x] Teach planner prompt to request needed code context.
- [x] Add structured planner output for lookup requests.
- [x] Execute requested lookup tools.
- [x] Save `files-inspected.md`.
- [x] Re-run planner with retrieved context.

## Phase 27: Context Pack Builder

- [x] Add `repo_context` stage.
- [x] Generate `context-pack.md`.
- [x] Include task, acceptance criteria, relevant files, snippets, and constraints.
- [x] Add line-numbered excerpts.
- [x] Add context-size caps.

## Phase 28: Project Context Chart MVP

- [ ] Generate `.nightshift/project-context-chart.md`.
- [ ] Include files, responsibilities, functions/classes, entry points, tests.
- [ ] Use simple regex/parser MVP.
- [ ] Update chart during planning.
- [ ] Store anchors/line numbers/search terms.

## Phase 29: Code Writer Stage

- [ ] Add `code_writer` stage type.
- [ ] Feed it task + context pack.
- [ ] Require unified diff output.
- [ ] Save `proposed.patch`.
- [ ] Save `implementation-summary.md`.

## Phase 30: Patch Normalization

- [ ] Add `patch_normalizer` stage.
- [ ] Support low-temperature formatter model.
- [ ] Convert messy model output to valid unified diff.
- [ ] Reject missing/ambiguous edits.
- [ ] Save `normalized.patch`.

## Phase 31: Patch Validation

- [ ] Parse unified diffs.
- [ ] Reject malformed patches.
- [ ] Enforce scoped paths.
- [ ] Reject path traversal.
- [ ] Enforce max files/max lines changed.
- [ ] Reject forbidden files.

## Phase 32: Patch Apply / Dry Run

- [ ] Add `patch_apply` stage.
- [ ] Support `mode: dry_run`.
- [ ] Support `mode: apply`.
- [ ] Save `applied.patch`.
- [ ] Preserve pre/post git status.
- [ ] Fail cleanly on apply errors.

## Phase 33: Test Feedback Repair Loop

- [ ] Feed test/static failure output back into implementer.
- [ ] Add bounded repair attempts.
- [ ] Save each repair patch.
- [ ] Save repair summaries.
- [ ] Stop after max retry count.

## Phase 34: End-to-End Coding Quickstart

- [ ] Update quickstart to modify real code.
- [ ] Include fake-agent test fixture.
- [ ] Demonstrate lookup → context pack → patch → apply → test.
- [ ] Document dry-run vs apply mode.
---

# Appendix A: Design Decisions and Rationale

## A.1 Local-first architecture

Decision:

* Prefer local models and local execution

Reasoning:

* Cheapness-first design
* Better experimentation
* Better privacy
* Reduced vendor dependency
* Better overnight scalability

---

## A.2 State machine over DAG

Decision:

* Use configurable state-machine workflows

Reasoning:

* One-task-at-a-time execution
* Retry loops are primary workflow behavior
* Easier auditing
* Easier debugging
* Simpler MVP

---

## A.3 YAML configuration

Decision:

* Use declarative YAML config

Reasoning:

* Human-readable
* Easier nested workflow representation
* Safer than arbitrary Python
* Better portability

---

## A.4 Cheapness-first model routing

Decision:

* Use expensive models selectively

Reasoning:

* Overnight pipelines can become token-expensive
* Local models are sufficient for many stages
* Review stages benefit more from premium models

---

## A.5 Strict repository scoping

Decision:

* Limit writable paths and executable commands

Reasoning:

* Prevent accidental damage
* Maintain trust in unattended execution
* Improve auditability

---

## A.6 Reviewable output over autonomy

Decision:

* Produce review packages rather than autonomous shipping

Reasoning:

* Human review remains critical
* Improves safety
* Improves correctness
* Keeps architecture grounded and practical

---

## A.7 Layered context model

Decision:

* Separate project, task, and retry context

Reasoning:

* Reduces token usage
* Prevents context explosion
* Improves signal quality
* Prevents recursive drift

---

## A.8 Artifact-heavy architecture

Decision:

* Persist plans, logs, reviews, outputs, and summaries

Reasoning:

* Debugging
* Prompt experimentation
* A/B testing
* Replayability
* Portfolio visibility

---

## A.9 No parallelism in v1

Decision:

* Execute one task at a time

Reasoning:

* Simpler correctness model
* Easier debugging
* Easier repository safety
* Easier context management

---

## A.10 Declarative pipelines first

Decision:

* No arbitrary Python hooks in v1

Reasoning:

* Safer execution
* Easier reproducibility
* Easier auditing
* Easier portability

---

# Closing Statement

NightShift is intended to explore a practical middle ground between:

* Fully manual software engineering
* Reckless autonomous agent systems

The system assumes that AI agents are useful but unreliable.

NightShift therefore treats agents as bounded workers inside deterministic, auditable, test-driven workflows.

The primary output is not blind autonomy.

The primary output is trustworthy leverage.
