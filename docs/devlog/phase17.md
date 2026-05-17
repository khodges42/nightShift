# Phase 17 Devlog: Local Model Backend

## Implemented

- Added first-class `backend: ollama` agent config support.
- Required `model` for Ollama agents.
- Kept `backend: command` unchanged.
- Reused the existing prompt bundle for Ollama.
- Invoked Ollama as `ollama run <model>` with prompt input on stdin.
- Persisted Ollama responses through the same agent artifact format.
- Added tests with mocked subprocess calls so Ollama is not required.

## Decisions Made

- Ollama is implemented as a local subprocess backend instead of an HTTP API wrapper.
- Missing Ollama executable returns a failed agent invocation artifact rather than crashing.
- Backend artifacts remain comparable across command and Ollama agents.

## Notes

- Real model quality and model availability are user environment concerns; tests do not require a running Ollama daemon.
