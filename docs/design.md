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

# 16. MVP Definition

The minimum viable NightShift implementation should:

1. Parse markdown tasks
2. Execute a declarative pipeline
3. Support local agents
4. Generate plans
5. Generate implementations
6. Run tests
7. Run static analysis
8. Run review agents
9. Retry failed stages
10. Produce artifacts
11. Produce an overnight summary
12. Restrict repository access

This MVP is sufficient to:

* Demonstrate orchestration architecture
* Demonstrate AI pipeline engineering
* Demonstrate safety-aware automation
* Serve as a strong portfolio project

---

# 17. MVP Implementation Status

The first MVP pass is implemented across phases 1 through 11.

Implemented capabilities:

* Project initialization
* Config validation
* Markdown task parsing
* Path and command safety checks
* Artifact storage
* Command stage execution
* Command-backed agent execution
* Deterministic pipeline execution
* Retry redirection and retry limits
* Context file creation and prompt injection
* Final task notes and run summaries
* README documentation

Known MVP limitations:

* Only the `command` agent backend is implemented
* `nightshift status` is still a placeholder
* Clean worktree enforcement is not fully wired
* Diff patch capture is not implemented
* Task completion mutation is not implemented
* Task dependency enforcement is not implemented
* Multi-task overnight batching is not implemented

---

# 18. Next Major Update Plan

The next major update should turn the single-task MVP into a more practical local runner while preserving the same safety and auditability model.

## Phase 12: Status Command

* [ ] Implement `nightshift status`
* [ ] Print config path and project root
* [ ] Print task counts
* [ ] Print next incomplete task
* [ ] Print latest run directory
* [ ] Print validation warnings where useful
* [ ] Add tests

Acceptance Criteria:

* User can inspect project state without running a pipeline
* Missing or malformed inputs produce clear errors
* Latest artifacts are discoverable from the CLI

---

## Phase 13: Git Safety and Diff Artifacts

* [ ] Implement clean-worktree enforcement when configured
* [ ] Capture pre-run git status
* [ ] Capture post-run git status
* [ ] Write `diff.patch`
* [ ] Include changed files in final reports
* [ ] Handle non-git repositories gracefully
* [ ] Add tests with temporary git repositories where practical

Acceptance Criteria:

* `require_clean_worktree: true` blocks dirty repositories
* Diffs are persisted after task execution
* Reports identify modified files without requiring users to inspect every artifact

---

## Phase 14: Task Completion Updates

* [ ] Mark completed tasks in `tasks.md`
* [ ] Preserve task file formatting where practical
* [ ] Avoid marking failed tasks complete
* [ ] Record task completion decisions in artifacts
* [ ] Add tests

Acceptance Criteria:

* Successful runs can mark `[ ]` tasks as `[x]`
* Failed runs leave tasks incomplete
* Task file updates are reviewable and minimal

---

## Phase 15: Multi-Task Run Mode

* [ ] Add `nightshift run --all`
* [ ] Process incomplete tasks in file order
* [ ] Stop or continue on failure based on config
* [ ] Create per-task artifact directories under one run
* [ ] Generate aggregate run summary
* [ ] Add tests

Acceptance Criteria:

* User can run more than one task unattended
* Each task remains independently reviewable
* Aggregate summary shows completed and failed tasks

---

## Phase 16: Dependency Handling

* [ ] Parse dependency bullets into structured task dependencies
* [ ] Block tasks whose dependencies are incomplete
* [ ] Detect missing dependency references
* [ ] Detect simple dependency cycles
* [ ] Report blocked tasks in status and run summaries
* [ ] Add tests

Acceptance Criteria:

* Tasks do not run before declared dependencies are complete
* Dependency errors are clear and actionable
* Task ordering remains deterministic

---

## Phase 17: Local Model Backend

* [ ] Add an Ollama-compatible agent backend
* [ ] Keep the existing command backend
* [ ] Reuse prompt bundle construction
* [ ] Persist request/response metadata
* [ ] Handle model errors and timeouts
* [ ] Add fake backend tests without requiring Ollama

Acceptance Criteria:

* Users can configure a local model backend for agent stages
* Tests do not require real model calls
* Agent artifacts remain comparable across backends

---

## Phase 18: Prompt and Pipeline Experiments

* [ ] Add prompt variant identifiers
* [ ] Snapshot prompt files per run
* [ ] Record agent backend metadata
* [ ] Add optional experiment labels to config
* [ ] Include experiment metadata in reports
* [ ] Add tests

Acceptance Criteria:

* Users can compare prompt/pipeline runs from artifacts
* Reports show which prompts and backend settings produced a result
* Experiment metadata does not change execution semantics

---

## Phase 19: Stronger Command Execution

* [ ] Replace shell-string execution where possible with parsed argv execution
* [ ] Preserve compatibility with explicit shell command stages when configured
* [ ] Add per-command timeout config
* [ ] Add environment variable allowlists
* [ ] Add working-directory restrictions
* [ ] Add tests

Acceptance Criteria:

* Command execution is safer by default
* Shell execution is explicit rather than implicit
* Command behavior remains auditable

---

## Phase 20: Documentation and Examples Refresh

* [ ] Add complete example project
* [ ] Add example fake-agent pipeline
* [ ] Add example local-model pipeline
* [ ] Document artifact review workflow
* [ ] Document troubleshooting
* [ ] Add config reference

Acceptance Criteria:

* New users can run a complete demo from a fresh checkout
* Documentation distinguishes implemented features from planned features
* Examples remain safe to run locally

---

## Phase 21: Read-Only Web Dashboard

* [ ] Add a Flask-based `nightshift web` command
* [ ] Read run state from `.nightshift/runs/`
* [ ] Show latest run summary
* [ ] Show task status and retry count
* [ ] Show stage results and artifact links
* [ ] Render markdown/plain-text artifacts safely
* [ ] Add simple auto-refresh
* [ ] Keep the dashboard read-only
* [ ] Add tests for route rendering and missing artifact handling

Acceptance Criteria:

* User can monitor a run from a browser without controlling execution
* Dashboard works from existing artifact files
* Missing or partial run artifacts do not crash the server
* No config, task, command, or pipeline mutation is exposed from the UI

Notes:

* This phase should avoid websockets and process control at first.
* The dashboard should be artifact-driven so it remains decoupled from pipeline internals.
* Start/stop controls, authentication, live log streaming, and approval gates are separate future work.

---

## Phase 22: Quickstart Test Project

* [ ] Add a guided quickstart project to `QUICKSTART.md`
* [ ] Recommend a small Python Lisp interpreter as the default test project
* [ ] Provide a multi-task `tasks.md` example
* [ ] Provide a matching `nightshift.yaml` example
* [ ] Provide suggested planner, implementer, and reviewer prompt files
* [ ] Include dependency examples across tasks
* [ ] Include commands for validation, `run --task`, and `run --all`
* [ ] Explain what artifacts the user should inspect after each run

Acceptance Criteria:

* A new user can create a small target repo and exercise NightShift end to end
* The project has multiple independently reviewable tasks
* Tasks are small enough for local/fake agents but realistic enough to test planning, implementation, tests, retries, artifacts, and dependencies
* The quickstart does not require external services

Recommended Project:

* A minimal Lisp interpreter in Python is a good test project because it is compact, incremental, testable, and naturally splits into parser, evaluator, environment, builtins, and error-handling tasks.

Alternative Projects:

* If the Lisp interpreter feels too language-theory focused, use a small INI/TOML-like config parser or a markdown todo CLI. Both are also compact and testable, but the Lisp interpreter gives better coverage of multi-step implementation and test generation.

---

## Phase 17-22 Implementation Status

Phases 17 through 22 are implemented.

Implemented capabilities:

* Ollama agent backend
* Experiment metadata and prompt snapshots
* Stronger command execution options
* Config reference, artifact review, and troubleshooting docs
* Read-only Flask dashboard entry point
* Complete quickstart Lisp example project

See `docs/devlog/phase17.md` through `docs/devlog/phase22.md` for implementation notes and decisions.

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
