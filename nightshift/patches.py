"""Unified diff extraction and validation."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
from pathlib import Path
import re
import subprocess

from .config import SafetyConfig
from .errors import PipelineError, SafetyError
from .safety import resolve_inside_root, resolve_project_root, validate_scoped_paths


DEFAULT_MAX_FILES = 20
DEFAULT_MAX_CHANGED_LINES = 2000
DEFAULT_FORBIDDEN_PATHS = (".git", ".nightshift", ".env")


@dataclass(frozen=True)
class PatchValidationResult:
    files: tuple[str, ...]
    changed_lines: int


@dataclass(frozen=True)
class PatchApplyResult:
    status: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    mode: str


@dataclass(frozen=True)
class FileUpdate:
    path: str
    content: str


def extract_unified_diff(text: str) -> str:
    fenced = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else text
    lines = candidate.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith("diff --git ")), None)
    if start is None:
        start = next((index for index, line in enumerate(lines) if line.startswith("--- ")), None)
    if start is None:
        raise PipelineError("Patch error: no unified diff found.")
    patch = "\n".join(lines[start:]).strip()
    if not patch:
        raise PipelineError("Patch error: unified diff is empty.")
    return patch + "\n"


def normalize_patch_text(text: str) -> str:
    patch = extract_unified_diff(text)
    if "@@" not in patch:
        raise PipelineError("Patch error: unified diff has no hunks.")
    return repair_hunk_counts(patch)


def repair_hunk_counts(patch: str) -> str:
    """Rewrite unified diff hunk counts from the actual hunk body."""

    lines = patch.splitlines()
    repaired: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("@@"):
            repaired.append(line)
            index += 1
            continue

        body: list[str] = []
        body_index = index + 1
        while body_index < len(lines):
            next_line = lines[body_index]
            if next_line.startswith("@@") or next_line.startswith("diff --git "):
                break
            body.append(next_line)
            body_index += 1
        repaired.append(_format_hunk_header(line, body, index + 1))
        repaired.extend(body)
        index = body_index
    return "\n".join(repaired).rstrip() + "\n"


def parse_file_updates(text: str) -> tuple[FileUpdate, ...]:
    """Parse model-supplied complete file content blocks."""

    updates: list[FileUpdate] = []
    pattern = re.compile(
        r"```(?:file|path)[:=](?P<path>[^\n`]+)\n(?P<content>.*?)```",
        flags=re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        path = match.group("path").strip()
        content = match.group("content")
        if not path:
            continue
        updates.append(FileUpdate(path=path, content=content))
    if not updates:
        raise PipelineError(
            "File writer error: no file blocks found. Expected fenced blocks like ```file:path.py."
        )
    return tuple(updates)


def generate_patch_from_file_updates(
    updates: tuple[FileUpdate, ...],
    project_root: str | Path,
    safety: SafetyConfig,
    forbidden_paths: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
) -> str:
    root = resolve_project_root(project_root)
    scoped_roots = validate_scoped_paths(root, safety.scoped_paths or (".",))
    patch_parts: list[str] = []
    seen: set[str] = set()
    for update in updates:
        normalized_path = _normalize_update_path(update.path)
        if normalized_path in seen:
            raise PipelineError(f"File writer error: duplicate file block `{normalized_path}`.")
        seen.add(normalized_path)
        _validate_patch_path(normalized_path, root, scoped_roots, forbidden_paths)
        file_path = resolve_inside_root(root, normalized_path, f"file update '{normalized_path}'")
        old_text = file_path.read_text(encoding="utf-8", errors="replace") if file_path.exists() else ""
        if old_text == update.content:
            continue
        patch_parts.extend(_diff_for_file(normalized_path, old_text, update.content, file_path.exists()))
    if not patch_parts:
        raise PipelineError("File writer error: generated patch has no changes.")
    return "\n".join(patch_parts).rstrip() + "\n"


def validate_patch(
    patch: str,
    project_root: str | Path,
    safety: SafetyConfig,
    max_files: int = DEFAULT_MAX_FILES,
    max_changed_lines: int = DEFAULT_MAX_CHANGED_LINES,
    max_delete_ratio: float | None = None,
    forbidden_paths: tuple[str, ...] = DEFAULT_FORBIDDEN_PATHS,
) -> PatchValidationResult:
    root = resolve_project_root(project_root)
    scoped_roots = validate_scoped_paths(root, safety.scoped_paths or (".",))
    files = _patch_files(patch)
    if not files:
        raise PipelineError("Patch validation failed: no changed files found.")
    if len(files) > max_files:
        raise PipelineError(f"Patch validation failed: touches {len(files)} files, max is {max_files}.")

    changed_lines = _changed_line_count(patch)
    deleted_lines = _deleted_line_count(patch)
    if changed_lines <= 0:
        raise PipelineError("Patch validation failed: patch has no changed lines.")
    if changed_lines > max_changed_lines:
        raise PipelineError(
            f"Patch validation failed: changes {changed_lines} lines, max is {max_changed_lines}."
        )
    if max_delete_ratio is not None and changed_lines > 0 and deleted_lines / changed_lines > max_delete_ratio:
        raise PipelineError(
            "Patch validation failed: deletion-heavy patch exceeds "
            f"max_delete_ratio {max_delete_ratio:.2f}."
        )

    for path_text in files:
        _validate_patch_path(path_text, root, scoped_roots, forbidden_paths)
    _validate_hunk_lines(patch)
    _validate_hunk_counts(patch)
    _validate_file_states(patch, root)
    return PatchValidationResult(files=tuple(sorted(files)), changed_lines=changed_lines)


def format_validation_result(result: PatchValidationResult) -> str:
    return "\n".join(
        [
            "# Patch Validation",
            "",
            "Status: pass",
            f"Changed files: {len(result.files)}",
            f"Changed lines: {result.changed_lines}",
            "",
            "## Files",
            "",
            *[f"- `{path}`" for path in result.files],
            "",
        ]
    )


def apply_patch_with_git(patch_path: Path, project_root: str | Path, mode: str = "dry_run") -> PatchApplyResult:
    root = resolve_project_root(project_root)
    command = ["git", "apply", "--ignore-whitespace", "--check", str(patch_path)]
    if mode == "apply":
        command = ["git", "apply", "--ignore-whitespace", str(patch_path)]
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return PatchApplyResult(
        status="pass" if completed.returncode == 0 else "fail",
        command=" ".join(command),
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        mode=mode,
    )


def format_patch_apply_result(result: PatchApplyResult, patch_path: str) -> str:
    return "\n".join(
        [
            "# Patch Apply",
            "",
            f"Status: {result.status}",
            f"Mode: {result.mode}",
            f"Patch: `{patch_path}`",
            f"Command: `{result.command}`",
            f"Exit code: {result.exit_code}",
            "",
            "## stdout",
            "",
            "```text",
            result.stdout.rstrip(),
            "```",
            "",
            "## stderr",
            "",
            "```text",
            result.stderr.rstrip(),
            "```",
            "",
        ]
    )


def _patch_files(patch: str) -> set[str]:
    files: set[str] = set()
    saw_hunk = False
    for line in patch.splitlines():
        if line.startswith("@@"):
            saw_hunk = True
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.add(_strip_prefix(parts[3]))
        elif line.startswith("+++ "):
            target = line[4:].strip()
            if target != "/dev/null":
                files.add(_strip_prefix(target))
        elif line.startswith("--- "):
            source = line[4:].strip()
            if source != "/dev/null":
                files.add(_strip_prefix(source))
    if not saw_hunk:
        raise PipelineError("Patch validation failed: unified diff has no hunk headers.")
    return {path for path in files if path}


def _validate_hunk_lines(patch: str) -> None:
    in_hunk = False
    for line_number, line in enumerate(patch.splitlines(), start=1):
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith(("+", "-", " ", "\\")):
            continue
        raise PipelineError(
            "Patch validation failed: malformed hunk line "
            f"{line_number}; expected a leading space, '+', '-', or backslash."
        )


def _validate_hunk_counts(patch: str) -> None:
    current: dict[str, int] | None = None

    def flush(line_number: int) -> None:
        if current is None:
            return
        old_expected = current["old_expected"]
        new_expected = current["new_expected"]
        old_actual = current["old_actual"]
        new_actual = current["new_actual"]
        hunk_line = current["line_number"]
        if old_actual != old_expected:
            raise PipelineError(
                "Patch validation failed: hunk starting at line "
                f"{hunk_line} old line count expected {old_expected}, got {old_actual} "
                f"before line {line_number}."
            )
        if new_actual != new_expected:
            raise PipelineError(
                "Patch validation failed: hunk starting at line "
                f"{hunk_line} new line count expected {new_expected}, got {new_actual} "
                f"before line {line_number}."
            )

    for line_number, line in enumerate(patch.splitlines(), start=1):
        if line.startswith("@@"):
            flush(line_number)
            current = _parse_hunk_header(line, line_number)
            continue
        if current is None:
            continue
        if line.startswith("diff --git "):
            flush(line_number)
            current = None
            continue
        if line.startswith("\\"):
            continue
        if line.startswith(" "):
            current["old_actual"] += 1
            current["new_actual"] += 1
        elif line.startswith("-"):
            current["old_actual"] += 1
        elif line.startswith("+"):
            current["new_actual"] += 1
    flush(len(patch.splitlines()) + 1)


def _parse_hunk_header(line: str, line_number: int) -> dict[str, int]:
    match = re.match(
        r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
        r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@",
        line,
    )
    if not match:
        raise PipelineError(
            f"Patch validation failed: malformed hunk header at line {line_number}."
        )
    old_count = int(match.group("old_count") or "1")
    new_count = int(match.group("new_count") or "1")
    return {
        "line_number": line_number,
        "old_expected": old_count,
        "new_expected": new_count,
        "old_actual": 0,
        "new_actual": 0,
    }


def _format_hunk_header(line: str, body: list[str], line_number: int) -> str:
    match = re.match(
        r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
        r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<section>.*)$",
        line,
    )
    if not match:
        raise PipelineError(
            f"Patch validation failed: malformed hunk header at line {line_number}."
        )
    old_count = 0
    new_count = 0
    for body_line in body:
        if body_line.startswith("\\"):
            continue
        if body_line.startswith(" "):
            old_count += 1
            new_count += 1
        elif body_line.startswith("-"):
            old_count += 1
        elif body_line.startswith("+"):
            new_count += 1
    return (
        f"@@ -{match.group('old_start')}{_format_count(old_count)} "
        f"+{match.group('new_start')}{_format_count(new_count)} @@"
        f"{match.group('section')}"
    )


def _format_count(count: int) -> str:
    return "" if count == 1 else f",{count}"


def _validate_file_states(patch: str, root: Path) -> None:
    current_path: str | None = None
    current_is_new = False
    current_is_deleted = False

    def flush() -> None:
        if not current_path:
            return
        target = root / current_path
        if current_is_new and target.exists():
            raise PipelineError(
                f"Patch validation failed: patch creates existing file `{current_path}`."
            )
        if current_is_deleted and not target.exists():
            raise PipelineError(
                f"Patch validation failed: patch deletes missing file `{current_path}`."
            )

    for line in patch.splitlines():
        if line.startswith("diff --git "):
            flush()
            parts = line.split()
            current_path = _strip_prefix(parts[3]) if len(parts) >= 4 else None
            current_is_new = False
            current_is_deleted = False
        elif line.startswith("new file mode "):
            current_is_new = True
        elif line.startswith("deleted file mode "):
            current_is_deleted = True
    flush()


def _changed_line_count(patch: str) -> int:
    count = 0
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk or line.startswith("\\"):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def _deleted_line_count(patch: str) -> int:
    count = 0
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if in_hunk and line.startswith("-") and not line.startswith("---"):
            count += 1
    return count


def _validate_patch_path(
    path_text: str,
    root: Path,
    scoped_roots: tuple[Path, ...],
    forbidden_paths: tuple[str, ...],
) -> None:
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise PipelineError(f"Patch validation failed: unsafe path `{path_text}`.")
    normalized = path.as_posix()
    for forbidden in forbidden_paths:
        forbidden_path = forbidden.strip("/\\")
        if normalized == forbidden_path or normalized.startswith(forbidden_path + "/"):
            raise PipelineError(f"Patch validation failed: forbidden path `{path_text}`.")
    try:
        resolved = resolve_inside_root(root, path, f"patch path '{path_text}'")
    except SafetyError as exc:
        raise PipelineError(f"Patch validation failed: {exc}") from exc
    for scoped_root in scoped_roots:
        try:
            resolved.relative_to(scoped_root)
            return
        except ValueError:
            continue
    scopes = ", ".join(item.relative_to(root).as_posix() for item in scoped_roots)
    raise PipelineError(
        f"Patch validation failed: path `{path_text}` is outside scoped paths: {scopes}."
    )


def _normalize_update_path(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").strip()
    if normalized.startswith(("a/", "b/")):
        normalized = normalized[2:]
    return normalized


def _diff_for_file(path: str, old_text: str, new_text: str, exists: bool) -> list[str]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    from_file = f"a/{path}" if exists else "/dev/null"
    to_file = f"b/{path}"
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=from_file,
            tofile=to_file,
            lineterm="",
        )
    )
    if not diff_lines:
        return []
    header = [f"diff --git a/{path} b/{path}"]
    if not exists:
        header.append("new file mode 100644")
    return [*header, *diff_lines]


def _strip_prefix(path_text: str) -> str:
    path = path_text.strip()
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path
