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

The pipeline uses model fallback ordering for implementation attempts:

1. `qwen2.5-coder:14b`
2. `carstenuhlig/omnicoder-9b`
3. `deepseek-coder-v2:16b`

Telemetry artifacts record which agent/model handled each stage and estimate token usage.

This template uses a TDD-oriented pipeline. It starts with a skeletal package, generates task-specific pytest tests from the current task acceptance criteria, reviews those tests for scope, and then implements only enough application code to pass them.
