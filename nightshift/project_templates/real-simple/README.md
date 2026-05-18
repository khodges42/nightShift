# Real Simple Template: Bookmark API

Use this template for a short, practical model-backed NightShift run.

```bash
nightshift init --template real-simple --root bookmarks-demo
cd bookmarks-demo
python -m pip install flask pytest
nightshift run --task TASK-001
```

The model is `qwen2.5-coder:14b` for planning, implementation, and review. The target is intentionally modest: a Flask + SQLite bookmark API with pytest coverage.

NightShift files live in `.nightshift/`. Application code should be created under `src/`, and tests under `tests/`.
