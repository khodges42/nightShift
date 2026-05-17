# Tutorial 01: Running NightShift With Real Local Models

This tutorial starts after the quickstart. The quickstart uses fake command agents so you can verify the pipeline deterministically. Here, you will replace those fake agents with real Ollama-backed agents and let a model generate a real patch.

The examples use `qwen2.5-coder:14b`, but any local coding model that can follow a strict unified-diff contract can be used.

## What You Will Build

You will run NightShift against a copy of the tiny Lisp example and use a local model to:

1. Inspect task and repository context.
2. Produce a plan.
3. Generate a unified diff.
4. Normalize and validate that patch.
5. Dry-run the patch.
6. Optionally apply the patch and run tests.

NightShift still controls the workflow. The model proposes code; NightShift validates and applies the patch.

## Prerequisites

Install NightShift from this repository:

```bash
python -m pip install -e .
```

Install and start Ollama, then make sure the model is available:

```bash
ollama pull qwen2.5-coder:14b
ollama list
```

Keep Ollama running. NightShift uses Ollama's local HTTP API, normally at `http://localhost:11434`, rather than the interactive `ollama run` terminal path.

## 1. Create a Scratch Target Project

Do not run apply-mode experiments directly against the checked-in example. Copy it somewhere disposable.

PowerShell:

```powershell
$NightShiftRepo = "C:\path\to\nightShift"
$TargetProject = "$HOME\Documents\tiny-lisp-model"
Copy-Item -Recurse "$NightShiftRepo\examples\quickstart-lisp" $TargetProject
Set-Location $TargetProject
```

Bash:

```bash
cp -r /path/to/nightShift/examples/quickstart-lisp ~/tiny-lisp-model
cd ~/tiny-lisp-model
```

Validate the copied project:

```bash
python -m nightshift.cli validate --config nightshift.yaml
```

## 2. Replace Fake Agents With Ollama Agents

Edit `nightshift.yaml`.

Replace the `agents:` section with:

```yaml
agents:
  planner:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.2
    system_prompt: agents/planner.md

  implementer:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.1
    system_prompt: agents/implementer.md

  reviewer:
    backend: ollama
    model: qwen2.5-coder:14b
    temperature: 0.1
    system_prompt: agents/reviewer.md
```

Then update the experiment labels:

```yaml
experiment:
  label: quickstart-lisp-real-model
  prompt_variant: ollama-qwen25-coder-14b-v1
```

## 3. Strengthen The Prompts

Real models need stricter instructions than fake fixtures.

Use this for `agents/planner.md`:

```markdown
You are the planning agent for NightShift.

Create a concise implementation plan for the current task.

If you need repository context before planning, output lookup requests exactly like this:

lookup_requests:
- tool: read_file
  path: relative/path.py
- tool: grep
  path: .
  pattern: search_regex

After context is provided, write a short plan with:
- files to edit
- tests to add or update
- risks

Do not write code.
```

Use this for `agents/implementer.md`:

```markdown
You are the implementation agent for NightShift.

Output only a unified diff.
Do not wrap the patch in markdown fences.
Do not include explanations before or after the patch.
Use diff --git headers.
Include tests when needed.
Keep the change as small as possible.
Only edit files needed for the task.
```

Use this for `agents/reviewer.md`:

```markdown
You are the review agent for NightShift.

Review the task, plan, patch artifacts, test output, and final state.

Output exactly:

status: pass | fail | retry | escalate
reason: <short explanation>
next_stage: <optional stage id>
context_update: <compact useful note>

Use retry when the implementation is close but needs another patch.
Use fail when the patch is unsafe, unrelated, or clearly broken.
Use pass only when the acceptance criteria are satisfied.
```

## 4. Start With Dry Run Mode

Before letting a model edit files, set patch apply to dry run.

In `nightshift.yaml`:

```yaml
- id: apply_patch
  type: patch_apply
  mode: dry_run
  output: patch-apply-output.txt
  on_fail: implement
```

Run one task:

```bash
python -m nightshift.cli run --config nightshift.yaml --task TASK-001
```

Inspect these artifacts:

```text
.nightshift/runs/<run-id>/run.log
.nightshift/runs/<run-id>/tasks/TASK-001/plan.md
.nightshift/runs/<run-id>/tasks/TASK-001/context-pack.md
.nightshift/runs/<run-id>/tasks/TASK-001/proposed.patch
.nightshift/runs/<run-id>/tasks/TASK-001/normalized.patch
.nightshift/runs/<run-id>/tasks/TASK-001/patch-validation.md
.nightshift/runs/<run-id>/tasks/TASK-001/patch-apply-output.txt
.nightshift/runs/<run-id>/tasks/TASK-001/final-notes.md
```

If a later stage routes back to `implement`, retry artifacts are written with attempt suffixes such as `repair-1.patch`, `normalized-1.patch`, `patch-validation-1.md`, `applied-1.patch`, and `patch-apply-output-1.txt`.

In dry-run mode, the patch should be validated and checked with `git apply --check`, but files should not change.

## 5. Apply The Patch

If the dry run looks good, switch to apply mode:

```yaml
- id: apply_patch
  type: patch_apply
  mode: apply
  output: patch-apply-output.txt
  on_fail: implement
```

Run again:

```bash
python -m nightshift.cli run --config nightshift.yaml --task TASK-001
```

If the model generates a valid patch, NightShift will:

- write `applied.patch`
- apply the patch with `git apply`
- run `python -m unittest discover -v`
- retry through the implementer if the test stage fails and `max_task_retries` allows it
- preserve per-attempt retry patch artifacts with numeric suffixes
- mark the task complete only if the pipeline completes

## 6. Monitor From The Web Dashboard

Install Flask if needed:

```bash
python -m pip install flask
```

Start the read-only dashboard:

```bash
python -m nightshift.cli web --config nightshift.yaml
```

Open the displayed local URL. The dashboard reads artifacts from `.nightshift/runs/` and shows the latest run summary and log tail.

## 7. Recommended First Settings

For real models, start conservatively:

```yaml
pipeline:
  max_task_retries: 3
  continue_on_task_failure: false
```

Patch validator:

```yaml
- id: validate_patch
  type: patch_validator
  output: patch-validation.md
  max_files: 4
  max_lines: 400
  on_fail: implement
  forbidden_paths:
    - .git
    - .nightshift
    - .env
```

Safety:

```yaml
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
```

Once you trust the workflow, consider setting `require_clean_worktree: true` in real repositories.

## Troubleshooting

If Ollama is unavailable:

```text
Agent exited with code 1
```

Confirm Ollama is running at the configured `base_url` and the model appears in `ollama list`.

If the model returns prose instead of a patch, tighten `agents/implementer.md`. The implementation stage requires a unified diff.

If patch validation fails, inspect:

```text
patch-validation.md
patch-validation-1.md
normalized.patch
normalized-1.patch
proposed.patch
repair-1.patch
```

If patch apply fails, inspect:

```text
patch-apply-output.txt
applied.patch
```

If tests fail, inspect:

```text
test-output.txt
repair-1.patch
repair-summary-1.md
```

Repair artifacts only appear when a later stage routes back to `implement` and the retry limit allows another attempt.

## What To Try Next

After `TASK-001` works:

```bash
python -m nightshift.cli run --config nightshift.yaml --all
```

Keep reviewing patches before trusting longer runs. The point of NightShift is not blind autonomy; it is controlled, reviewable leverage.
