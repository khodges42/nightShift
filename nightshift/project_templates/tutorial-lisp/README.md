# NightShift Imageboard Target

This project was created with:

```bash
nightshift init --template tutorial-imageboard
```

NightShift control files live in `.nightshift/`. Target application code should live under `src/`, tests under `tests/`, templates under `templates/`, and uploaded/generated static files under `static/`.

Install target dependencies:

```bash
python -m pip install flask pillow pytest
```

Validate the project:

```bash
nightshift validate
```

Run the first task:

```bash
nightshift run --task TASK-001
```
