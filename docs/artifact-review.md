# Artifact Review Workflow

Start with:

```text
.nightshift/runs/<run-id>/run-summary.md
```

Then inspect the task directory:

```text
.nightshift/runs/<run-id>/tasks/<task-id>/
```

Useful artifacts:

- `task.md`: task snapshot.
- `context.md`: compact task context.
- `plan.md`: planning agent output.
- `implementation-log.md`: implementation agent output.
- `test-output.txt`: command stage transcript.
- `review.md`: review agent output.
- `stage-results.md`: structured stage status summary.
- `context-out.md`: retry/context summary.
- `final-notes.md`: final task report.
- `diff.patch`: git diff when available.
- `git-status-before.txt` / `git-status-after.txt`: git state snapshots.
- `task-completion.md`: whether the task was marked complete.

Run-level artifacts:

- `config.snapshot.yaml`
- `run-metadata.md`
- `prompts/<agent>.md`
