# Writer And Coder Compatibility Audit

Date: 2026-05-22

## Summary

The recent writer workflow changes do not intentionally alter the code-generation templates or their stage routing.

During this audit, one possible shared-pipeline regression was found and fixed: generic `file_writer` stages were compacting large previous outputs on the first attempt. Since coding templates use `file_writer` for implementation, that could have reduced coding context before the implementer saw it. The behavior now preserves full first-attempt previous outputs while still stripping wrapped agent prompts from prior agent artifacts.

After that correction, the automated test suite passes.

## Writer Changes Reviewed

- Tutorial novel added a scene editor repair path:
  - failed continuity/style review routes to `edit_scene`
  - edited scene is normalized, validated, applied, then routed back to review
  - passing `style_review` skips editor and routes to `update_state`
- Tutorial novel prompts now include stricter pronoun and state-update guidance.
- State update file-writer stages receive focused current state context.
- Scene editor file-writer stages receive `current_scene_file`.
- Agent invocations now write a sibling JSON artifact for reliable stdout/stderr extraction.
- Pipeline config now supports optional `on_pass` routing.

## Coding Impact Findings

### Finding 1: Coding templates were not directly changed

No non-novel project template files changed in the current diff:

- `basic`
- `real-simple`
- `real-long-running`
- `tutorial-deaddrop`
- `tutorial-imageboard`
- `tutorial-lisp`

The new `editor` agent and review repair routing are only configured in `tutorial-novel/nightshift.yaml`.

### Finding 2: `on_pass` is inert for existing coding configs

`on_pass` defaults to `None`, so existing coding templates keep their prior linear pass behavior unless they explicitly opt in.

Passing review stages still ignore model-provided `next_stage` values. This preserves the existing safety behavior where reviewers cannot jump around the pipeline on a pass unless the config has an explicit `on_pass`.

### Finding 3: Code writer stages still use the same direct patch path

`code_writer` stages still:

- call the configured agent
- parse stdout as a unified diff
- support lookup-request reruns
- write implementation summaries
- feed patch normalizer/validator/apply stages as before

The JSON agent artifact change only changes how NightShift reads agent stdout internally; it does not change the prompt contract or patch contract.

### Finding 4: File-writer implementers had one possible context regression; fixed

Potential issue found:

- `_file_writer_previous_outputs` had started compacting large previous outputs even on first attempt.
- Coding templates such as DeadDrop use `file_writer` for implementation.
- That could have shortened planner/context output before the implementer saw it.

Fix applied:

- First-attempt `file_writer` stages now preserve full previous outputs.
- Retry attempts still compact large previous outputs to control prompt bloat.
- Wrapped agent artifacts still strip down to stdout so old prompts do not pollute later prompts.

Regression coverage added:

- `test_file_writer_first_attempt_preserves_large_previous_outputs`

### Finding 5: State/editor special context branches are narrowly gated

The new context enrichment branches are guarded by stage shape:

- state update branch only applies to `file_writer` stages whose allowed paths are state files:
  - `story/plot-state.md`
  - `story/characters.md`
  - `story/timeline.md`
  - `story/unresolved-threads.md`
- scene editor branch only applies to `file_writer` stages whose id starts with `edit_` and whose allowed paths include `story/chapters`

Normal coding implementer stages such as `implement`, `implement_junior`, and `implement_senior` do not match either branch.

## Template Validation Notes

Validated successfully:

- `basic`
- `tutorial-deaddrop`
- `tutorial-novel`

Validation still fails for these templates because `debugger` is configured but `.nightshift/agents/debugger.md` is missing:

- `real-simple`
- `real-long-running`
- `tutorial-imageboard`
- `tutorial-lisp`

Those failures are not caused by the writer changes; there is no current diff in those template directories.

## Verification

Focused tests:

```powershell
python -m pytest tests/test_pipeline.py tests/test_config.py tests/test_agents.py -q
```

Result:

```text
71 passed, 4 subtests passed
```

Full suite:

```powershell
python -m pytest -q
```

Result:

```text
196 passed, 4 subtests passed
```

## Conclusion

After the first-attempt file-writer context fix, I do not see evidence that the writer workflow changes degrade code generation. The shared changes are either opt-in (`on_pass`), artifact-reading improvements (JSON stdout), or narrowly gated to novel state/editor stages.

Remaining non-writer issue: several coding-oriented templates still reference a missing `debugger.md` prompt. That should be handled separately from this writer/coder compatibility pass.
