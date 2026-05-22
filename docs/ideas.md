# Ideas TODO

This file tracks open ideas only. Completed items should be removed after they land.

Priority scale:

- P0: do next; directly improves current feedback loop
- P1: important after the current loop is usable
- P2: useful, but only after basics are stable
- P3: defer or maybe reject

## P1: Add Test Governance For Generated Tests

Use this only for generated-test mode. Do not put generated tests back into the default DeadDrop fixed-test pipeline yet.

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
- no future-task keywords unless accepted by current task acceptance criteria

Then optional model reviewer checks acceptance-criteria alignment.

## P0: Preserve Good Drafts During Repair

When a generated file block contains useful allowed content plus disallowed or invalid extra content, avoid redrafting from scratch.

Possible behavior:

- keep the allowed candidate file artifact
- strip disallowed file blocks only when configured as safe for that stage
- continue with validation for the allowed content
- or ask the model for a minimal correction that preserves the accepted candidate

For writing workflows, preserving a good scene is more valuable than forcing a full retry.

## P0: Remove Runtime Overrides For Custom Ollama Models

If a model is a tuned local Ollama model such as `nightshift-writer` or `nightshift-base`, prefer the Modelfile parameters unless the stage has a specific reason to override them.

Candidate config cleanup:

- remove `temperature`
- remove `num_ctx`
- remove `num_predict`
- remove `stop` if present

This avoids NightShift accidentally overriding tuned custom-model behavior.

## P1: Improve `what-happened` For Model Runs

The report should identify usable intermediate work, not only final failure state.

Examples:

- model produced a valid scene candidate
- validation rejected extra state files
- recover candidate from `candidate-files/<stage>/index.md`
- retry output was invalid or too short
- next recommended action

This should make failed creative-writing runs reviewable without manually reading every artifact.

## P1: Add Stage-Specific Task Views

The same task may say both "write scene" and "update state", but those responsibilities belong to different stages.

Stage prompts should receive a filtered task view:

- drafter sees only scene-writing criteria
- state updater sees only durable state update criteria
- reviewers see criteria relevant to their review role

This reduces prompt contradiction and makes deterministic stage rules easier for models to follow.

## P1: Preserve Intra-Attempt Rerun Artifacts

When NightShift re-runs an agent inside the same stage attempt, do not overwrite the previous artifact.

Examples:

- `draft_scene-agent-output.md`
- `draft_scene-agent-output-invalid-rerun-1.md`
- `draft_scene-agent-output-1.md`

This keeps the initial useful output visible even when strict rerun output is worse.

## P1: Add A Writing-Mode Validator

Add deterministic checks for prose workflows:

- scene file exists at requested path
- scene word count is within configured range
- drafter did not touch state files
- state updater did not touch chapter prose
- no TODOs, author notes, or bracket placeholders
- optional checks for repeated headings or accidental prompt leakage

This should run before model review stages.

## P2: Add A Test Analyzer Agent For TDD

Defer until generated tests are stable.

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

This may help smaller models, but it is another model output that can be wrong. Add it only after the fixed-test pipeline works through all DeadDrop tasks.

## P2/P3: Add A Test Planner

Maybe, but defer.

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

## P2: Add Run Comparison

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

## P2: Add A Separate Multiagent/Fallback DeadDrop Experiment

Keep the default DeadDrop template boring and deterministic:

```text
planner -> semantic_context -> context -> implement -> validate -> test -> review
```

If fallback is useful, put it in a separate experiment template, for example:

```text
tutorial-deaddrop-multiagent
```

or:

```text
examples/templates/multiagent-fallback
```

Reason:

- fallback makes artifacts harder to reason about
- model variability is bad while debugging pipeline behavior
- the default template should remain the reliability harness
