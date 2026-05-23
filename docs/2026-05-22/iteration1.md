# Iteration 1: SCENE-002 Update State Failure

Date: 2026-05-22

## Run Reviewed

- Sandbox: `integ_runs/20260522T214944.385761Z`
- Run: `.nightshift/runs/20260522T215005.188534Z`
- Task: `SCENE-002`
- Final status: failed
- Failed stage: `update_state`

## What Happened

The scene workflow mostly succeeded:

- `draft_scene` wrote the scene.
- `continuity_review` correctly failed the first draft for pronoun drift.
- `edit_scene` repaired the pronoun issue.
- `continuity_review` passed after edit.
- `style_review` passed.

The remaining failure happened in `update_state`.

NightShift reported:

```text
File writer error: no file blocks found. Expected FILE: path with ---CONTENT---/---END--- or fenced blocks like ```file:path.py.
```

The model output did contain visible `FILE:` blocks, but it omitted the required `---END---` delimiter. It emitted:

```text
FILE: story/plot-state.md
---CONTENT---
...

FILE: story/characters.md
---CONTENT---
...
```

The current parser requires `---END---`, so it rejected all of the blocks.

## Additional Risk Found

The rejected state update also tried to rewrite character canon in unsafe ways:

- It changed BLOODMONEY's pronoun reference to `he/him`.
- It changed Cricket's pronoun reference to `they/them`.
- It compressed/replaced larger parts of `story/characters.md`.

That means simply accepting unterminated blocks is not enough. The parser can be more tolerant, but the state updater still needs stronger constraints so durable canon does not drift.

## Suggested Fixes

Short-term fixes for this iteration:

1. Make `parse_file_updates` tolerate delimiter blocks that omit `---END---` when a new `FILE:` block or EOF clearly terminates the previous block.
2. Keep strict path validation and duplicate-file validation unchanged.
3. Strengthen the state-updater prompt:
   - never edit `Pronouns / Reference` sections
   - preserve existing character profiles
   - prefer updating `plot-state.md`, `timeline.md`, and `unresolved-threads.md`
   - edit `characters.md` only for small additive current-status facts
4. Add regression tests for unterminated delimiter parsing.

Longer-term follow-up:

- Add deterministic writing-state validation that rejects changes to protected canon sections such as `Pronouns / Reference`.
- Move character canon into structured data so pronoun constraints can be validated directly.

## Planned Changes

- Update delimiter block parsing in `nightshift/patches.py`.
- Add parser tests in `tests/test_patches.py`.
- Tighten `state-updater.md` in the tutorial novel template.
- Run focused parser tests and the full suite.

## Changes Made

- `parse_file_updates` now accepts delimiter-style file blocks that omit `---END---` when the next `FILE:` header or EOF clearly terminates the block.
- Added regression coverage for:
  - unterminated delimiter blocks before another `FILE:`
  - mixed terminated and unterminated delimiter blocks
- Strengthened the tutorial novel state updater prompt to protect character canon:
  - never change `Pronouns / Reference`
  - never change canonical pronouns, narrative reference, identity, or core wound
  - prefer state/timeline/thread files over `characters.md`
  - edit `characters.md` only for small additive current-status facts or new named characters
- Added deterministic protection in file-block patch generation:
  - changes to existing `Pronouns / Reference` sections in `story/characters.md` are rejected before a patch is generated
- Added regression coverage for rejecting protected pronoun canon changes.

## Verification

Focused tests:

```powershell
python -m pytest tests/test_patches.py tests/test_pipeline.py -q
```

Result:

```text
56 passed
```

Full suite:

```powershell
python -m pytest -q
```

Result:

```text
199 passed, 4 subtests passed
```
