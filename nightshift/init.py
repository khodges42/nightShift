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


def init_project(root: Path, force: bool = False) -> list[Path]:
    """Create starter NightShift files under root.

    Existing files are left untouched unless force is true.
    """

    root = root.resolve()
    targets = [root / relative for relative in STARTER_FILES]
    existing = [path for path in targets if path.exists()]
    if existing and not force:
        formatted = ", ".join(str(path.relative_to(root)) for path in existing)
        raise InitError(
            "Initialization would overwrite existing files. "
            f"Use --force to replace: {formatted}"
        )

    written: list[Path] = []
    for relative, content in STARTER_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    return written
