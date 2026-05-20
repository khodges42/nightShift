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

The MVP and the patch-capable local runner are implemented.

NightShift currently provides:

* `nightshift init` for starter project generation
* `nightshift validate` for config, prompt, task, dependency, path, and command validation
* `nightshift status` for read-only project inspection
* `nightshift run` for the next runnable incomplete task
* `nightshift run --task TASK-ID` for a specific task
* `nightshift run --all` for sequential multi-task execution
* `nightshift web` for a read-only artifact dashboard
* Operational run logging to the CLI, per-run logs, and aggregate logs
* Markdown task parsing with descriptions, acceptance criteria, completion state, and dependency bullets
* Dependency validation for missing references and simple cycles
* Dependency-aware task selection and task blocking
* Declarative YAML pipeline execution
* Command, agent, agent-review, review, summarize, repo-context, code-writer, file-writer, patch-normalizer, patch-validator, and patch-apply stage handling
* Retry redirection with a configured task retry limit
* Command-backed agents
* Ollama-backed local model agents through the local HTTP API
* OpenAI-compatible local/server model agents
* Per-agent temperature settings
* Cost, runtime, retry, and estimated token telemetry summaries
* Scoped repo lookup tools: `list_files`, `read_file`, and `grep`
* Lightweight semantic repository indexing for files, symbols, imports, tests, and compact task context
* Planner lookup requests, `files-inspected.md`, and planner reruns with retrieved context
* Project context chart generation
* Context pack generation
* Unified diff code-writing contract
* Deterministic diff generation from model-supplied complete file blocks
* Patch normalization, deterministic hunk-count repair, validation, dry-run, and apply modes
* Per-attempt retry patch artifacts such as `repair-1.patch`, `normalized-1.patch`, and `patch-validation-1.md`
* Test/static failure repair loops via bounded stage retries
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
* Documentation for config, artifact review, troubleshooting, quickstart, and patch workflows
* A complete fake-agent patch-mode quickstart Lisp example under `examples/quickstart-lisp/`
* A deterministic pastebin tutorial template with model fallback configuration

The system remains sequential and local-first. It is designed to produce reviewable artifacts and repository state, not to deploy, push, or autonomously ship changes.


# 16.5 Current Tasks Todo

- [x] TASK-001: Failure classification pipeline

Dependencies:
- None

Description:
Add a deterministic post-failure analysis stage that runs after every failed command or test execution. The classifier should inspect stdout/stderr, exit codes, modified files, and failing tests, then categorize the failure and recommend the next orchestration action.

Acceptance Criteria:
- Captures stdout, stderr, exit code, modified files, and failing test names
- Produces structured output containing:
  - failure category
  - probable root cause
  - confidence
  - recommended next action
  - retry recommendation
- Supports initial categories:
  - syntax/import error
  - missing dependency
  - missing resource/fixture
  - environment/config issue
  - API misuse
  - test expectation mismatch
  - logic bug
  - stuck/unclear
- Integrates into orchestration pipeline before retries occur
- Includes tests for classification behavior


- [x] TASK-002: Structured blocked/resource request system

Dependencies:
- TASK-001

Description:
Allow agents to explicitly declare missing resources or environmental requirements instead of endlessly retrying implementation attempts. Add structured "blocked" responses and runtime support for generating common fixtures and test resources.

Acceptance Criteria:
- Supports structured blocked responses such as:
  - missing fixture
  - missing config
  - missing database
  - missing asset
- Includes fixture generators for:
  - PNG/JPG images
  - JSON fixtures
  - sqlite databases
  - text/blob files
- Runtime can automatically satisfy supported requests
- Generated fixtures are isolated to the active run directory
- Includes tests for fixture generation and blocked flow handling


- [x] TASK-003: Dedicated debugger agent role

Dependencies:
- TASK-001

Description:
Introduce a dedicated debugger agent responsible for diagnosis rather than implementation. The debugger reviews failed attempts and provides concise explanations and recommendations for the implementer.

Acceptance Criteria:
- Debugger receives:
  - task description
  - current patch
  - failure output
  - recent attempt history
- Debugger outputs:
  - concise diagnosis
  - recommended next action
  - "do not modify" guidance
- Debugger does not directly modify code initially
- Implementer receives debugger output in retry context
- Includes tests for debugger orchestration behavior


- [x] TASK-004: Stuck detection and escalation policy engine

Dependencies:
- TASK-001
- TASK-003

Description:
Detect retry churn loops and automatically escalate to different models, debugger review, or human intervention when progress stalls.

Acceptance Criteria:
- Tracks:
  - repeated failures
  - repeated file edits
  - unchanged failing tests
  - expanding diff size
  - oscillating implementations
- Supports configurable retry budgets
- Supports escalation policies such as:
  - debugger review
  - larger local model
  - cloud model
  - human review
- Stops infinite retry loops
- Includes tests for churn detection and escalation behavior


- [x] TASK-005: Multi-model orchestration and escalation

Dependencies:
- TASK-004

Description:
Add support for multiple implementation and debugging models with configurable routing, retry budgets, and escalation rules. Provide examples

Acceptance Criteria:
- Supports separate model pools for:
  - implementers
  - debuggers
  - escalation models
- Allows configurable retry budgets per model
- Supports configurable temperatures per role
- Allows fallback ordering between models
- Integrates with escalation policy engine
- Includes tests for model routing and escalation flow


- [x] TASK-006: Dependency management agent

Dependencies:
- TASK-001

Description:
Add a dependency management subsystem capable of detecting missing packages, understanding dependency manifests, and automatically resolving installation issues. Just for python now.

Acceptance Criteria:
- Detects:
  - missing imports
  - missing packages
  - dependency manifest drift
  - invalid package references
- Supports:
  - pip
  - uv
  - poetry
  - requirements.txt
  - pyproject.toml
- Can propose or apply dependency fixes
- Can retry runs after dependency installation
- Includes tests for dependency resolution flows


- [x] TASK-007: Patch governor and diff safety system

Dependencies:
- TASK-004

Description:
Prevent runaway architectural rewrites and unrelated modifications during retry loops by analyzing diffs and rejecting unsafe patches.

Acceptance Criteria:
- Detects:
  - unrelated file modifications
  - excessive diff growth
  - deletion-heavy patches
  - architecture drift
- Can reject unsafe patches before commit/application
- Produces actionable rejection feedback for implementers
- Supports configurable thresholds and policies
- Includes tests for diff analysis and patch rejection behavior


- [x] TASK-008: Integration sandbox runner

Dependencies:
- None

Description:
Add a one-command integration environment runner that creates isolated timestamped run directories for NightShift testing and orchestration experiments. This is the equivalent of doing --template with the tutorials

Acceptance Criteria:
- Adds command:
  - `nightshift integ-run`
- Creates timestamped run directories under:
  - `integ_runs/`
- Automatically:
  - creates isolated venv
  - installs project dependencies
  - initializes clean template/project state
- Adds `integ_runs/` to `.gitignore`
- Persists:
  - logs
  - transcripts
  - patches
  - generated artifacts
- Supports cleanup policies for old runs
- Includes tests for sandbox creation and cleanup behavior


- [x] TASK-009: Structured retry memory system

Dependencies:
- TASK-001
- TASK-004

Description:
Persist compact structured summaries of previous attempts to prevent retry amnesia and repeated failed approaches.

Acceptance Criteria:
- Stores:
  - attempted fixes
  - failure causes
  - rejected hypotheses
  - successful observations
- Produces compact retry summaries instead of raw log dumps
- Retry summaries are injected into implementer context
- Supports configurable memory compaction
- Includes tests for retry memory summarization behavior


- [x] TASK-010: Environment-aware execution diagnostics

Dependencies:
- TASK-001
- TASK-006

Description:
Improve orchestration awareness of environment-level failures versus implementation-level failures to reduce wasted retries and false debugging paths.

Acceptance Criteria:
- Distinguishes:
  - environment failures
  - dependency failures
  - fixture/resource failures
  - implementation logic failures
- Prevents implementation retries when environment is invalid
- Surfaces actionable remediation guidance
- Integrates with failure classifier and dependency manager
- Includes tests for environment diagnostic behavior

- [x] TASK-011: Update tutorials to reflect the previous changes to the templates as needed

Description:
Tutorials should have the newly added features when relevant.,

Acceptance Criteria:
- Tutorials have features

- [x] TASK-012: Stage output should be more organized. Right now run/task/ produces many files and it is difficult to keep track of. Either sub folders for retries, appending for retries, or compacting, whichever makes sense for our use case.

- [x] TASK-013: Cost, token, and runtime telemetry

Dependencies:
- TASK-005

Description:
Track orchestration cost, latency, retry counts, token usage, and success rates across agents and models. Generally telemetry for analyzing model efficiency and usage. Which model fixes bugs fastest?

Acceptance Criteria:
- Tracks token usage per agent and run
- Tracks runtime duration and retry counts
- Records success/failure metrics
- Supports per-model statistics
- Exposes telemetry summaries and reports
- Includes tests for telemetry aggregation

- [x] TASK-014: Repository semantic indexing system

Dependencies:
- None

Description:
Build lightweight semantic indexing over repositories so agents can retrieve relevant files, symbols, tests, and architecture context without loading excessive raw context.

Acceptance Criteria:
- Indexes symbols, files, imports, and tests
- Supports semantic and keyword search
- Returns compact relevant context snippets
- Reduces prompt context size
- Includes tests for retrieval quality


- [x] TASK-015: Pastebin tutorial project template

Dependencies:
- TASK-008
- TASK-005

Description:
Add a new tutorial project template for NightShift based on a small Pastebin/snippet-hosting service. This should work like the existing imageboard tutorial, but be simpler, more deterministic, and easier to use for testing agent orchestration. The template should be creatable with `--template`.

Acceptance Criteria:
- Adds a new template named `pastebin`
- Supports creating the tutorial project with a command such as:
  - `nightshift init --template tutorial-pastebin`
- Template includes a small but realistic app with:
  - snippet creation
  - snippet viewing
  - snippet listing
  - optional expiration field
  - tags or language field
  - basic search/filtering
- Includes a test suite with multiple incremental tasks suitable for agent testing
- Avoids complex media/file-upload behavior from the imageboard tutorial
- Uses deterministic fixtures and simple dependencies
- Includes clear task descriptions for the agent to complete
- Includes README instructions explaining the tutorial goals
- Supports model fallback ordering for this template:
  - `qwen2.5-coder:14b`
  - `carstenuhlig/omnicoder-9b`
  - `deepseek-coder-v2:16b`
- If the first model fails or exceeds its retry budget, the next fallback model is attempted
- Records which model handled each attempt
- Includes tests for template creation and model fallback configuration
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
          files-inspected.md
          context-pack.md
          proposed.patch
          normalized.patch
          patch-validation.md
          applied.patch
          patch-apply-output.txt
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
* Flask is optional; `nightshift web` requires it to be installed.
* Model backends depend on the user's local model server, Ollama installation, or command wrappers.
* Git artifacts can be unavailable or degraded in non-git repositories or repositories blocked by Git safe-directory rules.
* Task mutation is intentionally minimal and only flips matching checklist lines.
* Patch application currently uses `git apply`; non-git workflows are limited.
* Command configuration remains string-first for compatibility.
* There is no branch isolation, resumable run state machine, approval workflow, or deployment integration.

---

# 18. Active Roadmap

Completed phase checklists are removed from this design document once they are reflected in the implemented baseline and user-facing docs. Track future phase work here only while it is active, using concise implementation notes when a decision needs durable context.

The next important additions are:

1. Branch isolation for patch runs
   Run each task on a dedicated branch or worktree, record branch metadata, and make rollback/review safer.

2. Resumable run state
   Persist machine-readable run state so interrupted runs can continue from the last completed stage instead of restarting.

3. Human approval gates
   Add optional approval stages before patch apply, after failed validation, or before task completion.

4. Structured patch policy config
   Move max files, max lines, forbidden paths, allowed file types, binary rejection, and protected files into a reusable project-level write policy.

5. Better model backend support
   Expand OpenAI-compatible behavior, add request metadata artifacts, support response format hints, and document local server patterns. Machine-readable Ollama output now uses the HTTP API instead of the interactive `ollama run` terminal path; keep this non-terminal capture policy for future model backends where exact patch text matters.

6. Deterministic edit formats beyond full files
   The `file_writer` stage now generates unified diffs from complete file blocks. Future work should add smaller structured edit descriptions for large files while preserving deterministic diff generation.

7. Retry artifact versioning
   Continue improving per-attempt artifact preservation. Patch retries now preserve files such as `repair-1.patch`, `normalized-1.patch`, and `patch-validation-1.md`; future work should add richer latest-attempt indexes and dashboard navigation.

8. Patch repair stage
   Hunk counts are now deterministically recomputed during normalization for direct unified diff output. Future work should add an explicit patch repair stage for malformed hunk bodies that receives the invalid patch, validation error, and relevant source excerpts, then returns a complete replacement patch. This stage should remain bounded by strict validation and should not silently guess intent for arbitrary malformed hunks.

9. Richer dashboard
   Add task/stage navigation, patch views, validation status, run log tail, and artifact links without adding mutation controls.

10. Project context chart improvements
   Use language-aware parsers where available, include import graphs, ownership hints, and stale-context detection.

11. Stronger repair feedback
   Feed compact test/static failure summaries, patch apply errors, and reviewer objections into repair attempts with clearer bounded policies.

12. End-to-end apply-mode examples
   Add more small target projects and fake-agent fixtures that exercise patch apply, repair, validation failure, and review retry paths.

13. Packaging and dependency extras
   Add optional extras such as `nightshift[web]`, document supported Python versions, and prepare the project for repeatable installation.

Implementation note:

Recent local-model patch experiments exposed repeated line-fragment artifacts where long generated lines were split and the tail was duplicated on the following line. This affected prose and unified diffs, producing malformed hunk lines that strict validation correctly rejected. Treat this as a backend/output-capture and patch-contract problem before adding editor or linter agents: avoid terminal streaming for machine output, preserve retry artifacts, and prefer deterministic diff generation when exact syntax matters.
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
