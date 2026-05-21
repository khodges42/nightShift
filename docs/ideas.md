# Ideas TODO

This file is now prioritized inline. Priority scale:

- P0: do next; directly improves current feedback loop
- P1: important after the current loop is usable
- P2: useful, but only after basics are stable
- P3: defer or maybe reject

## P0: Make Integration Tests Easy To Run

Status: implemented.

Implemented command:

```powershell
python -m nightshift.cli integ-test --template tutorial-pastebin --task TASK-001
```

It creates the integration sandbox, sets up the venv, runs validation through setup, runs the task from the generated project directory, and prints the artifact root. Use `--dry-run` to preview the setup and task command.

Running integration tests is still too manual.

Current process:

- install the current version of NightShift
- run `python -m nightshift.cli integ-run --template tutorial-pastebin --setup`
- copy the activation line from the output and run it
- `cd` into the generated directory
- run the task there, because running from the repo root does not find `nightshift.yaml`

Recommendation: implement a wrapper command, not just a loose script.

Target command:

```powershell
python -m nightshift.cli integ-test --template tutorial-pastebin --task TASK-001
```

It should:

1. create the integration run
2. set up the venv
3. install NightShift from the current checkout
4. run `nightshift validate`
5. run the selected task from the generated project directory
6. print final status and artifact path

Useful variants:

```powershell
python -m nightshift.cli integ-test --template tutorial-pastebin --all
python -m nightshift.cli integ-test --template tutorial-pastebin --task TASK-002 --keep 3
```

The base-directory config issue may not be a core bug, but it is bad UX. The wrapper should handle `cwd` correctly.

## P0/P1: Remove Multi-Candidate Workflow From Default Pastebin

Status: implemented for the default pastebin template and tutorial example.

Original idea:

- The multi-candidate workflow does not add as much as expected.
- Keep it as an example, maybe `example-multiagent`.

Recommendation: yes. Remove it from the default pastebin tutorial.

Reason:

- Pastebin is becoming the reliability harness.
- Multi-candidate fallback makes artifacts harder to reason about.
- It adds model variability while we are still debugging pipeline behavior.

Better split:

```text
tutorial-pastebin
tutorial-pastebin-multiagent
```

or:

```text
examples/templates/multiagent-fallback
```

Default pastebin should be boring:

```text
planner -> semantic_context -> context -> implement -> validate -> test -> review
```

Use one strong implementer first. Add fallback only in a separate experiment template.

## P1: Add A Qwen3 / 30B Pastebin Variant

Status: implemented as the default pastebin model path using `qwen3-coder:30b`.

Original idea:

- Use a non-coder model for planner roles.
- Try `qwen3.6:27b` for planning.
- Use `qwen3-coder:30b` for implementer and code-heavy roles.

Recommendation: viable, but make this a variant, not the default.

kass reply- No lets make this the default. the qwen3-coder:30b is fast now for me for some reason.

Suggested template/config:

```text
tutorial-pastebin-qwen3
```

Possible role split:

- planner: `qwen3.6:27b`
- reviewer/debugger: `qwen3.6:27b`
- implementer: `qwen3-coder:30b` or exact local 30B coder model name

Important: confirm exact model names with:

```powershell
ollama list
```

i did its `qwen3-coder:30b`

Use 30B where it pays:

- first implementation for hard tasks
- repair after concrete test failure
- schema/database changes
- multi-file changes

Do not blindly make every stage 30B if it is slow.

reply: Its not slow now!`qwen3-coder:30b`
 
## P2: Expose More Model Parameters

Status: implemented for the practical first set.

Supported optional Ollama fields now include `num_ctx`, `num_predict`, `seed`, and `stop`, in addition to existing `temperature`.

Original question:

- What else besides temperature is available?
- Are any worth optimizing?

Likely useful for Ollama:

- `temperature`
- `num_ctx`
- `num_predict`
- `seed`
- `stop`
- maybe `top_p`, `top_k`, `repeat_penalty`

Recommendation: add only a small practical set first.

Useful config shape:

```yaml
temperature: 0.1
num_ctx: 8192
num_predict: 4096
seed: 1
```

Most useful:

- `num_ctx`: larger repo/task context
- `num_predict`: caps runaway output
- `seed`: reproducibility, if supported consistently
- `temperature`: already useful; keep low for code
- `stop`: could help enforce file-block or diff-only contracts

Defer tuning `top_p`, `top_k`, and `repeat_penalty` unless a specific model needs it.

reply: yup lets put this in the nightshift.yaml (optional parameters, if they arent in there that's fine, but we should offer them.)

## P1: Add Test Governance For Generated Tests

Original idea:

- Have a test governance layer for when agents write tests.
- A reviewer validates alignment with acceptance criteria.

Recommendation: yes, but only for generated-test mode. Do not put generated tests back into default pastebin yet.

The previous failures proved test-writing agents will:

- edit app code
- import nonexistent modules
- require undeclared dependencies
- inspect implementation internals
- write tests for future behavior

Governance should be deterministic first, model-reviewed second.

Deterministic checks:

- test-writing stage may only touch `tests/`
- tests compile
- tests import only allowed public interfaces
- tests do not import undeclared dependencies
- tests do not define Flask routes or app implementation
- test names match current task id or current artifact
- no future-task keywords unless accepted by current task AC

Then optional model reviewer checks acceptance-criteria alignment.

## P2: Add A Test Analyzer Agent For TDD

Original idea:

- Analyze tests.
- Translate them into direct instructions for the implementer.
- Maybe implement using agent YAML definitions without new NightShift features.

Recommendation: viable, but defer until generated tests are stable.

Possible pipeline:

```text
write_tests -> validate_tests -> analyze_tests -> implement
```

Analyzer output should be concrete:

```text
Implementation requirements:
- create_app(database_path) must return a Flask app.
- POST /snippets must return 201 and JSON id.
- GET /snippets/<id> must return persisted fields.

Do not modify:
- tests/test_task001.py
```

This may help smaller models, but it is another model output that can be wrong. Add it only after the fixed-test pipeline works through all pastebin tasks.

## P2/P3: Add A Test Planner

Original idea:

- A test planner understands acceptance criteria and code.
- Provides input to the next stage about constraints and code, especially for non-TDD.

Recommendation: maybe, but defer.

This overlaps with:

- planner
- test analyzer
- test governance

Too many planning-ish stages can make the pipeline bloated and contradictory.

If implemented later, keep it focused:

```text
test_planner -> write_tests -> test_governance -> implement
```

For now, fold this idea into the future test governance/analyzer work.

## P1: Add Fixed Tests For All Pastebin Tasks

Status: mostly implemented in the template.

Current fixed tests:

```text
tests/test_task001.py
tests/test_task002.py
tests/test_task003.py
tests/test_task004.py
tests/test_task005.py
```

Important design:

```yaml
python -m pytest -q tests/test_{task_id_compact}.py
```

This lets all future task tests exist without breaking earlier tasks.

Next step: validate these through integration runs, one task at a time.

## P1: Add `nightshift integ-report`

Status: implemented as a first-pass artifact summarizer.

New idea.

Summarize latest integration run across tasks:

```text
TASK-001 complete in 1 retry
TASK-002 failed at validate_patch
Root cause: protected tests modified
Artifacts: ...
```

Right now we inspect artifacts manually. NightShift should do more of that.

Possible command:

```powershell
python -m nightshift.cli integ-report --latest
```

## P1: Add Task-Test Preflight To `validate`

Status: implemented.

`nightshift validate` now renders task command placeholders for every task and fails early if a configured `tests/test_*.py` path is missing.

Partially implemented at run time.

Current behavior:

- task command placeholders can render paths like `tests/test_task002.py`
- `run_task` preflight fails before invoking agents if the task-specific test file is missing

Better behavior:

```powershell
nightshift validate
```

should warn or fail:

```text
TASK-003 expects tests/test_task003.py and it exists.
TASK-004 expects tests/test_task004.py and it exists.
```

This catches missing fixed tests earlier.

## P2: Add Run Comparison

New idea.

Useful once comparing 14B vs 30B:

```powershell
nightshift compare-runs --latest 5
```

Show:

- model
- task
- retries
- failure stage
- final reason
- runtime
- token estimate

This should come after `integ-test` and `integ-report`.

