# Phase 20 Devlog: Documentation and Examples Refresh

## Implemented

- Added `docs/config-reference.md`.
- Added `docs/artifact-review.md`.
- Added `docs/troubleshooting.md`.
- Added a complete `examples/quickstart-lisp/` project.
- Updated quickstart docs to point users at the example project.

## Decisions Made

- Documentation now distinguishes command and Ollama agent backends.
- The example project uses fake command agents so it can run without external services.
- The quickstart Lisp project is included as a target repo example rather than baked into NightShift runtime behavior.

## Notes

- The example is intended for pipeline testing and artifact review, not as a full Lisp implementation.
