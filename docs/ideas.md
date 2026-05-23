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

## P1: Classify Writing Review Failures For Repair Routing

The tutorial novel now has a short-term editor stage for review failures, but review failures should eventually be classified before routing.

Candidate classes:

- `local_edit`: pronoun drift, small continuity issue, missing beat, light style correction
- `redraft`: wrong premise, broken scene structure, impossible chronology, severe acceptance mismatch
- `escalate`: ambiguous canon conflict or user preference needed

Route `local_edit` to the editor, `redraft` to the drafter, and `escalate` to a clear user-facing failure. Keep original draft and edited draft artifacts side by side for comparison.

## P1: Separate Expressive Drafting From Corrective Editing

If writing quality feels lower after adding stricter correctness constraints, test a two-pass creative workflow:

```text
free_draft -> corrective_edit -> review
```

The drafter would receive fewer mechanical constraints and focus on voice, scene energy, imagery, and character presence. A later editor pass would enforce:

- output format
- canonical pronouns
- continuity details
- acceptance criteria
- minor cleanup

This may recover stronger prose while keeping correctness guarantees. Treat it as an experiment, not a default, because weaker local models may use the looser draft prompt as permission to ignore task boundaries.

## P1: Add A Writing-Mode Validator

Add deterministic checks for prose workflows:

- scene file exists at requested path
- scene word count is within configured range
- drafter did not touch state files
- state updater did not touch chapter prose
- no TODOs, author notes, or bracket placeholders
- optional checks for repeated headings or accidental prompt leakage

This should run before model review stages.

## P1: Use Structured State Events For Writing Workflows

Replace model-written full state-file rewrites with compact structured state events, then let NightShift deterministically merge them into durable files such as:

- `story/plot-state.md`
- `story/characters.md`
- `story/timeline.md`
- `story/unresolved-threads.md`

Candidate state updater output:

```yaml
events:
  - file: story/plot-state.md
    section: Completed Scenes
    add:
      - SCENE-001 complete; Saint and Miette introduced.
  - file: story/unresolved-threads.md
    section: Open Threads
    add:
      - Saint depends emotionally on Miette and needs compute tokens to keep her present.
```

NightShift would validate allowed files/sections, reject unknown targets, and apply append/update operations deterministically. This avoids asking a writing model to rewrite entire durable state files after every scene.

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

## P2: Adopt Useful Fork Ideas From rsarv3006

Source: https://github.com/rsarv3006/nightShift/commit/649eef65546a4ae648170bf29663f939eb031d2c

Author: GitHub user `rsarv3006`

Useful ideas to consider porting:

- Add `on_status` stage routing so review stages can route `pass`, `retry`, `fail`, and `escalate` to different follow-up stages.
- Add configurable repo lookup exclusions, for example `safety.skip_repo_parts`, so projects can hide generated or irrelevant directories from planner/reviewer context tools.
- Add configurable agent timeout, for example `pipeline.agent_timeout_seconds`, so long local-model runs can be tuned per project.
- Add docs and focused tests around status-based routing behavior.
