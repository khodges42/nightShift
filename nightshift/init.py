"""Project initialization helpers."""

from __future__ import annotations

from pathlib import Path

from .errors import InitError
from . import templates


STARTER_FILES = {
    "nightshift.yaml": templates.NIGHTSHIFT_YAML,
    "tasks.md": templates.TASKS_MD,
    "agents/planner.md": templates.PLANNER_PROMPT,
    "agents/implementer.md": templates.IMPLEMENTER_PROMPT,
    "agents/reviewer.md": templates.REVIEWER_PROMPT,
}

IMAGEBOARD_FILES = {
    "nightshift.yaml": templates.IMAGEBOARD_NIGHTSHIFT_YAML,
    ".nightshift/tasks.md": templates.IMAGEBOARD_TASKS_MD,
    ".nightshift/agents/planner.md": templates.REAL_MODEL_PLANNER_PROMPT,
    ".nightshift/agents/implementer.md": templates.REAL_MODEL_IMPLEMENTER_PROMPT,
    ".nightshift/agents/reviewer.md": templates.REAL_MODEL_REVIEWER_PROMPT,
    "README.md": templates.IMAGEBOARD_README,
    "src/imageboard/.gitkeep": "",
    "tests/.gitkeep": "",
    "templates/.gitkeep": "",
    "static/uploads/.gitkeep": "",
    "static/thumbs/.gitkeep": "",
}

PROJECT_TEMPLATES = {
    "basic": STARTER_FILES,
    "imageboard": IMAGEBOARD_FILES,
}


def init_project(root: Path, force: bool = False, template: str = "basic") -> list[Path]:
    """Create starter NightShift files under root.

    Existing files are left untouched unless force is true.
    """

    root = root.resolve()
    if template not in PROJECT_TEMPLATES:
        known = ", ".join(sorted(PROJECT_TEMPLATES))
        raise InitError(f"Unknown template '{template}'. Available templates: {known}")
    files = PROJECT_TEMPLATES[template]
    targets = [root / relative for relative in files]
    existing = [path for path in targets if path.exists()]
    if existing and not force:
        formatted = ", ".join(str(path.relative_to(root)) for path in existing)
        raise InitError(
            "Initialization would overwrite existing files. "
            f"Use --force to replace: {formatted}"
        )

    written: list[Path] = []
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    return written
