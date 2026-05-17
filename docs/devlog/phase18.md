# Phase 18 Devlog: Prompt and Pipeline Experiments

## Implemented

- Added optional `experiment.label` and `experiment.prompt_variant` config fields.
- Snapshotted agent prompt files into `runs/<run-id>/prompts/`.
- Wrote `run-metadata.md` with project, experiment, agent backend, model, command, and prompt metadata.
- Included experiment metadata in final task reports and run summaries.
- Added tests for experiment config loading and prompt/metadata artifact creation.

## Decisions Made

- Experiment metadata is descriptive only and does not alter execution semantics.
- Prompt snapshots are per-run, not per-task, because agent definitions are run-level configuration.

## Notes

- This creates enough metadata to compare prompt/backend runs from artifacts without adding a database.
