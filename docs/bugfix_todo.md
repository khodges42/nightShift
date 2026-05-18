# Bugfix TODO

## Some kind of tool install feature

Continually fails on flask_sqlalchemy until I install that.

## Tutorial need to include . directory for imageboard

## Git status artifacts are noisy for non-git repositories

Observed artifact:

```text
# Git Status before

Available: false
Exit code: 128

fatal: not a git repository (or any of the parent directories): .git
```

Current behavior:

- NightShift continues when `require_clean_worktree: false`.
- `git-status-before.txt`, `git-status-after.txt`, and `diff.patch` may contain git errors.
- This is technically safe, but confusing for users running quickstart/demo projects outside git.

Desired behavior:

- Detect non-git repositories explicitly.
- Write a clearer artifact message such as:

```text
Git repository: false
Clean-worktree enforcement: skipped because require_clean_worktree is false
Diff artifact: unavailable because project is not a git repository
```

- Avoid treating non-git as a scary-looking failure when clean worktree is not required.

Acceptance criteria:

- Non-git projects produce readable git artifacts without fatal-looking output.
- `require_clean_worktree: true` still fails safely in non-git projects.
- Reports mention that git metadata/diff is unavailable because the project is not a git repo.

## Git safe.directory / ownership conflicts on Windows

Observed context:

- Git can report dubious ownership or safe-directory errors when a repo was created or managed by a different Windows user identity.
- This may happen when using GitHub Desktop, WSL, admin shells, or multiple Windows accounts.

Current behavior:

- NightShift records the raw git error in artifacts.
- If `require_clean_worktree: true`, NightShift blocks execution.
- If `require_clean_worktree: false`, NightShift continues but git status/diff artifacts can look like hard failures.

Desired behavior:

- Detect common `dubious ownership` / `safe.directory` messages.
- Write a clearer explanation in artifacts and reports.
- Suggest the exact remediation outside NightShift, for example:

```powershell
git config --global --add safe.directory <project-root>
```

Acceptance criteria:

- Safe-directory failures are classified separately from ordinary git failures.
- Users get actionable guidance.
- NightShift does not attempt to change global git config automatically.

## Clarify docs around git requirements

Add to `QUICKSTART.md` and troubleshooting:

- Git is optional when `require_clean_worktree: false`.
- Git is required for clean-worktree enforcement and useful diffs.
- Non-git projects can still run pipelines.
- Git ownership/safe-directory errors affect git artifacts, not core task execution, unless clean-worktree enforcement is enabled.

## Console appears idle during long agent calls

Current behavior:

- Long Ollama calls can make `nightshift run` look frozen.
- Progress is only visible by inspecting `.nightshift/` artifacts or `ollama ps`.

Desired behavior:

- Print stage start/finish messages to the console.
- Include agent id, stage id, task id, and artifact path when available.
- Do not stream model output yet; just show lifecycle progress.

Acceptance criteria:

- User can tell which stage is running.
- Long-running model calls no longer look like a hung process.

## Ollama output can make review stages fail if not structured

Current behavior:

- Review stages require `status: pass | fail | retry | escalate`.
- General-purpose model output may include prose before/after the structured fields.
- If no valid status is found, the review stage fails.

Desired behavior:

- Keep strict structured review parsing, but improve prompt templates and error messages.
- Artifact should clearly say the review output was unparseable and show the expected contract.

Acceptance criteria:

- Failed review parsing is easy to diagnose from `review.md` and `stage-results.md`.

## `echo` fake agents do not behave consistently across shells

Current behavior:

- Starter templates use `command: echo`.
- Depending on shell/platform, `echo` may not preserve stdin or may only echo arguments.
- This can make fake agent artifacts less useful.

Desired behavior:

- Replace fake-agent defaults with small Python one-liners or documented fake-agent scripts.
- Keep examples cross-platform.

Acceptance criteria:

- Starter project produces predictable fake-agent output on Windows PowerShell/cmd and Unix shells.

## `unittest discover` behavior depends on test package layout

Current behavior:

- Python 3.14 returned `NO TESTS RAN` with exit code 5 for an example project until `tests/__init__.py` was added.
- Users may hit the same issue in fresh target repos.

Desired behavior:

- Document this in troubleshooting.
- Consider making quickstart templates include `tests/__init__.py`.

Acceptance criteria:

- Quickstart test command works in a fresh copied example.
- Troubleshooting mentions what to do if `NO TESTS RAN` appears.

## Task completion can mark tasks complete even if no source changed

Current behavior:

- A pipeline can pass with fake agents and passing tests, then mark the task complete.
- This is expected for fake/demo mode but surprising when users expect code edits.

Desired behavior:

- Add a warning when a task completes and git/diff detects no source changes, where git is available.
- Documentation should explain fake-agent mode vs editing-agent mode.

Acceptance criteria:

- Users are less likely to mistake artifact generation for code modification.

## Dashboard requires Flask but dependency is optional

Current behavior:

- `nightshift web` fails with a helpful message if Flask is missing.
- README mentions `pip install flask`, but install extras are not defined.

Desired behavior:

- Add an optional dependency group such as `nightshift[web]` later.
- Keep graceful error behavior.

Acceptance criteria:

- Users have one documented install command for dashboard support.
