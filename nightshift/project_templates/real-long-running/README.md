# Real Long-Running Template: Junior/Senior Pipeline

Use this template for a realistic, longer NightShift run where several agents cooperate on a non-trivial service task.

```bash
nightshift init --template real-long-running --root incident-service
cd incident-service
python -m pip install flask pytest
nightshift run --task TASK-001
```

Use case: build and evolve a small incident intake and triage service with Flask, SQLite, tests, and audit history.

Agents:

- Planner: `qwen2.5-coder:14b`
- Architect: `qwen2.5-coder:14b`
- Junior implementer: `qwen2.5-coder:14b`
- Senior implementer: `qwen3-coder:30b`
- Reviewer: `qwen2.5-coder:14b`

Junior/senior routing:

- The junior implementer tries first.
- Patch validation, patch apply, or tests can route directly to `implement_senior`.
- The junior reviewer prompt asks the reviewer to jump to `summarize` when the junior passes, or to `implement_senior` when the junior needs escalation.
- The senior path then writes its own patch artifacts, applies, tests, and reviews.

This template intentionally has a longer pipeline and a bigger blast radius. Use it after the simple template works on your machine.
