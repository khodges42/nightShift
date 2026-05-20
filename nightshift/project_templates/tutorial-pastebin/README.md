# NightShift Pastebin Tutorial

This template is a small deterministic snippet-hosting service for testing NightShift orchestration.

Create it with:

```bash
nightshift init --template tutorial-pastebin
```

Or create an isolated integration sandbox from the NightShift repository root:

```bash
python -m nightshift.cli integ-run --template tutorial-pastebin
cd integ_runs/<timestamp>/project
```

Activate the generated virtual environment.

PowerShell:

```powershell
..\.venv\Scripts\Activate.ps1
python -m pip install -e ..\..\..
```

Bash:

```bash
source ../.venv/bin/activate
python -m pip install -e ../../..
```

Install target dependencies:

```bash
python -m pip install -e . pytest flask
```

Validate and run:

```bash
nightshift validate
nightshift run --task TASK-001
```

When running from an integration sandbox, the same commands are run inside `integ_runs/<timestamp>/project`.

The pipeline uses model fallback ordering for implementation attempts:

1. `qwen2.5-coder:14b`
2. `carstenuhlig/omnicoder-9b`
3. `deepseek-coder-v2:16b`

Telemetry artifacts record which agent/model handled each stage and estimate token usage.
