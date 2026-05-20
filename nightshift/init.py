"""Project initialization helpers."""

from __future__ import annotations

from pathlib import Path
import shutil

from .errors import InitError
from . import templates


STARTER_FILES = {
    "nightshift.yaml": templates.NIGHTSHIFT_YAML,
    "tasks.md": templates.TASKS_MD,
    "agents/planner.md": templates.PLANNER_PROMPT,
    "agents/implementer.md": templates.IMPLEMENTER_PROMPT,
    "agents/reviewer.md": templates.REVIEWER_PROMPT,
    "agents/debugger.md": templates.DEBUGGER_PROMPT,
}

IMAGEBOARD_FILES = {
    "nightshift.yaml": templates.IMAGEBOARD_NIGHTSHIFT_YAML,
    ".nightshift/tasks.md": templates.IMAGEBOARD_TASKS_MD,
    ".nightshift/agents/planner.md": templates.REAL_MODEL_PLANNER_PROMPT,
    ".nightshift/agents/implementer.md": templates.REAL_MODEL_IMPLEMENTER_PROMPT,
    ".nightshift/agents/reviewer.md": templates.REAL_MODEL_REVIEWER_PROMPT,
    ".nightshift/agents/debugger.md": templates.REAL_MODEL_DEBUGGER_PROMPT,
    "README.md": templates.IMAGEBOARD_README,
    "src/imageboard/.gitkeep": "",
    "tests/.gitkeep": "",
    "templates/.gitkeep": "",
    "static/uploads/.gitkeep": "",
    "static/thumbs/.gitkeep": "",
}

PROJECT_TEMPLATES = {
    "basic": STARTER_FILES,
    "tutorial-imageboard": IMAGEBOARD_FILES,
}

TEMPLATE_ROOT = Path(__file__).resolve().parent / "project_templates"


def available_templates() -> tuple[str, ...]:
    names = set(PROJECT_TEMPLATES)
    if TEMPLATE_ROOT.exists():
        names.update(path.name for path in TEMPLATE_ROOT.iterdir() if path.is_dir())
    return tuple(sorted(names))


def init_project(root: Path, force: bool = False, template: str = "basic") -> list[Path]:
    """Create starter NightShift files under root.

    Existing files are left untouched unless force is true.
    """

    root = root.resolve()
    if template not in available_templates():
        known = ", ".join(available_templates())
        raise InitError(f"Unknown template '{template}'. Available templates: {known}")
    template_dir = TEMPLATE_ROOT / template
    files = _template_files(template, template_dir)
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
        if content is None:
            source = template_dir / relative
            shutil.copyfile(source, path)
        else:
            path.write_text(content, encoding="utf-8")
        written.append(path)

    return written


def _template_files(template: str, template_dir: Path) -> dict[str, str | None]:
    if template_dir.exists():
        return {
            path.relative_to(template_dir).as_posix(): None
            for path in sorted(template_dir.rglob("*"))
            if path.is_file()
        }
    return PROJECT_TEMPLATES[template]
