"""Project context chart generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import SafetyConfig
from .safety import resolve_project_root, validate_scoped_paths


CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".yaml", ".yml", ".toml"}


@dataclass(frozen=True)
class FileChart:
    path: str
    responsibility: str
    functions: tuple[str, ...]
    classes: tuple[str, ...]
    anchors: tuple[str, ...]
    is_entry_point: bool
    is_test: bool


def build_project_context_chart(project_root: str | Path, safety: SafetyConfig, max_files: int = 200) -> str:
    root = resolve_project_root(project_root)
    scoped_roots = validate_scoped_paths(root, safety.scoped_paths or (".",))
    files: list[Path] = []
    for scoped_root in scoped_roots:
        if scoped_root.is_file():
            candidates = [scoped_root]
        else:
            candidates = [item for item in scoped_root.rglob("*") if item.is_file()]
        for candidate in candidates:
            if _skip(candidate, root):
                continue
            if candidate not in files:
                files.append(candidate)

    charts = [_chart_file(path, root) for path in sorted(files)[:max_files]]
    return format_project_context_chart(charts, truncated=max(0, len(files) - max_files))


def format_project_context_chart(charts: list[FileChart], truncated: int = 0) -> str:
    lines = ["# Project Context Chart", ""]
    if not charts:
        lines.append("No project files found.")
        return "\n".join(lines)

    lines.extend(["## Entry Points", ""])
    entry_points = [chart for chart in charts if chart.is_entry_point]
    lines.extend(f"- `{chart.path}`: {chart.responsibility}" for chart in entry_points)
    if not entry_points:
        lines.append("- None detected")

    lines.extend(["", "## Tests", ""])
    tests = [chart for chart in charts if chart.is_test]
    lines.extend(f"- `{chart.path}`" for chart in tests)
    if not tests:
        lines.append("- None detected")

    lines.extend(["", "## Files", ""])
    for chart in charts:
        lines.extend(
            [
                f"### `{chart.path}`",
                "",
                f"- Responsibility: {chart.responsibility}",
                f"- Entry point: {str(chart.is_entry_point).lower()}",
                f"- Test file: {str(chart.is_test).lower()}",
                f"- Functions: {', '.join(chart.functions) if chart.functions else 'None detected'}",
                f"- Classes: {', '.join(chart.classes) if chart.classes else 'None detected'}",
                f"- Anchors/search terms: {', '.join(chart.anchors) if chart.anchors else 'None detected'}",
                "",
            ]
        )
    if truncated:
        lines.append(f"Truncated {truncated} additional files.")
    return "\n".join(lines)


def _chart_file(path: Path, root: Path) -> FileChart:
    relative = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    functions: list[str] = []
    classes: list[str] = []
    anchors: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        function = re.match(r"\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        js_function = re.match(r"\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        klass = re.match(r"\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", line)
        if function:
            name = function.group(1)
            functions.append(f"{name}@L{line_number}")
            anchors.append(name)
        elif js_function:
            name = js_function.group(1)
            functions.append(f"{name}@L{line_number}")
            anchors.append(name)
        elif klass:
            name = klass.group(1)
            classes.append(f"{name}@L{line_number}")
            anchors.append(name)

    return FileChart(
        path=relative,
        responsibility=_responsibility(relative, lines),
        functions=tuple(functions),
        classes=tuple(classes),
        anchors=tuple(dict.fromkeys(anchors[:12])),
        is_entry_point=_is_entry_point(relative, text),
        is_test=_is_test(relative),
    )


def _responsibility(relative: str, lines: list[str]) -> str:
    for line in lines[:12]:
        stripped = line.strip().strip("#").strip()
        if stripped and not stripped.startswith(("from ", "import ")):
            return stripped[:140]
    if _is_test(relative):
        return "Test coverage."
    return "Source or project support file."


def _is_entry_point(relative: str, text: str) -> bool:
    name = Path(relative).name.lower()
    return name in {"cli.py", "main.py", "__main__.py"} or "if __name__ == \"__main__\"" in text


def _is_test(relative: str) -> bool:
    parts = relative.lower().split("/")
    name = parts[-1]
    return "tests" in parts or name.startswith("test_") or name.endswith("_test.py")


def _skip(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    parts = set(relative.parts)
    if ".git" in parts or ".nightshift" in parts or "__pycache__" in parts:
        return True
    return path.suffix.lower() not in CODE_EXTENSIONS
