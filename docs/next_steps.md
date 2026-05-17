# Next Steps: Editing Agent Support

NightShift currently orchestrates agent prompts, command execution, artifacts, reports, retries, and context. It does not yet apply code changes by itself.

To make NightShift actually edit code, add an implementation application layer between agent output and test execution.

Current behavior:

```text
prompt -> model/command -> implementation-log.md
```

Desired editing behavior:

```text
prompt -> model/command -> proposed patch -> validate patch -> apply patch -> capture diff -> run tests
```

## 1. Define an Edit Contract

The implementer needs to output a machine-usable edit format rather than freeform prose.

Best first contract:

```text
unified diff patch
```

NightShift should accept one clear patch format and reject everything else. This matters because model output often includes commentary, markdown fences, partial files, or invalid patches.

## 2. Add Patch Extraction and Validation

NightShift needs to extract a proposed edit from implementer output and validate it before touching the repository.

Validation should check:

- patch is present
- patch only touches paths inside the project root
- patch only touches configured scoped paths
- patch does not touch `.git/`, `.nightshift/`, secrets, or config unless allowed
- patch does not delete large unrelated files
- patch applies cleanly
- patch size is reasonable
- binary changes are rejected initially

## 3. Add a Patch Applier

Once a patch passes validation, NightShift applies it.

Practical first option:

```text
git apply --check
git apply
```

This is easier than writing a patch engine, but it means editing mode depends on git.

Artifacts should include:

```text
proposed.patch
patch-apply-output.txt
diff.patch
```

## 4. Separate Implementation Generation From Patch Application

Do not make the agent executor silently edit files.

Better pipeline shape:

```text
plan
review_plan
implement
apply_patch
test
static
review
```

The implementer generates an artifact. A deterministic NightShift stage validates and applies it. This keeps model output separate from repository mutation.

## 5. Define Failure and Retry Behavior

If patch application succeeds but tests fail, NightShift needs an explicit policy.

Safest early behavior:

```text
apply patch
run tests
if tests fail, keep changes and artifacts
retry by generating another patch against current state
```

More advanced behavior could reverse failed patches, but that requires stronger state tracking.

## 6. Feed Patch and Test Failures Into Retry Context

Retry context should include compact facts such as:

- previous patch failed to apply because X
- tests failed with Y
- reviewer objected to Z
- files changed so far

This makes retries useful without dumping full transcripts into prompts.

## 7. Tighten Write Safety

Editing needs stricter safety than logging.

Add:

- writable path allowlist
- protected paths
- max patch size
- max files changed
- max line count changed
- no symlink following outside root
- no writes to `.git`, `.nightshift`, virtualenvs, or lockfiles unless allowed
- optional clean-worktree requirement before editing

The current path safety is a start, but editing needs a dedicated write policy.

## 8. Update Prompts

The implementer prompt should require exact patch output.

Example:

```text
Output only a unified diff.
Do not include markdown fences.
Do not include explanation.
Only edit files needed for the task.
Include tests when needed.
```

The reviewer should review the actual diff and test output, not just prose.

## 9. Add Editing Safety Tests

Important test cases:

- valid patch applies
- invalid patch fails cleanly
- patch outside root is rejected
- patch touching forbidden path is rejected
- patch with no changes is rejected
- failed apply writes artifacts
- failed tests still produce reports
- retry receives patch failure context
- task is not marked complete unless patch, tests, and review pass

## 10. Decide on Editing Modes

There are two possible editing modes.

### Patch Mode

The model emits a patch. NightShift validates and applies it.

Pros:

- auditable
- safer
- deterministic application
- easy to review

Cons:

- models sometimes emit malformed patches

### Command Editing Mode

An agent command directly edits files.

Pros:

- works with tools like Codex CLI or Claude Code
- more capable

Cons:

- harder to sandbox
- harder to know what happened without before/after diffs
- needs stronger git and diff capture

Recommended path:

1. Implement patch mode first.
2. Add command editing mode later behind stricter safety and artifact capture.

Core principle:

```text
Agents propose.
NightShift disposes.
```

The agent should not be trusted to mutate the repository directly until NightShift has a strong audit and safety layer around that mutation.
