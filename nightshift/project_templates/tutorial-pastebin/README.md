# NightShift Pastebin Tutorial

This template is a small deterministic snippet-hosting service for testing NightShift orchestration.

Create it with:

```bash
nightshift init --template tutorial-pastebin
```

Or create an isolated integration sandbox from the NightShift repository root:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin
```

To create, set up, validate, and run one task in a single command:

```bash
python -m nightshift.cli integ-test --template tutorial-pastebin --task TASK-001
```

To create the sandbox and set it up in one step:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin --setup
```

Then set up the generated Python project:

```bash
python -m nightshift.cli integ-setup --project integ_runs/<timestamp>/project
```

`integ-setup` cannot activate the venv for your current shell. In PowerShell, activate it manually if you want plain `python` and `nightshift` to use the integration venv:

```powershell
integ_runs\<timestamp>\.venv\Scripts\Activate.ps1
```

For a normal non-integration checkout, install target dependencies:

```bash
python -m pip install -e . pytest flask
```

Validate and run:

```bash
nightshift validate
nightshift run --task TASK-001
nightshift what-happened
```

When running from an integration sandbox, the same commands are run inside `integ_runs/<timestamp>/project`.

The default pastebin pipeline uses `qwen3-coder:30b` for planning, implementation, debugging, test review, and final review. It intentionally does not use multi-candidate fallback; pastebin is the deterministic reliability harness.

Telemetry artifacts record which agent/model handled each stage and estimate token usage.

This template uses fixed task-specific pytest files. The pipeline starts with a skeletal package, implements only the current task, runs `tests/test_{task_id_compact}.py`, and then reviews the result.
