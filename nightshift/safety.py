"""Safety helpers for paths and commands."""

from __future__ import annotations

from pathlib import Path

from .errors import SafetyError


def resolve_project_root(root: str | Path) -> Path:
    """Resolve and validate a project root directory."""

    resolved = Path(root).resolve()
    if not resolved.exists():
        raise SafetyError(f"Safety error: project root does not exist: {resolved}")
    if not resolved.is_dir():
        raise SafetyError(f"Safety error: project root is not a directory: {resolved}")
    return resolved


def resolve_inside_root(root: str | Path, path: str | Path, context: str = "path") -> Path:
    """Resolve a path and reject values outside the project root."""

    resolved_root = resolve_project_root(root)
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SafetyError(
            f"Safety error: {context} resolves outside project root: {path}"
        ) from exc
    return resolved


def validate_scoped_paths(root: str | Path, scoped_paths: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
    """Validate that every configured scoped path remains inside the root."""

    return tuple(
        resolve_inside_root(root, scoped_path, f"scoped path '{scoped_path}'")
        for scoped_path in scoped_paths
    )


def safe_artifact_path(
    root: str | Path,
    artifact_dir: str | Path,
    *parts: str | Path,
    create_parent: bool = False,
) -> Path:
    """Build an artifact path that cannot escape the configured artifact tree."""

    artifact_root = resolve_inside_root(root, artifact_dir, "artifact directory")
    path = artifact_root
    for part in parts:
        candidate = Path(part)
        if candidate.is_absolute():
            raise SafetyError(f"Safety error: artifact path segment must be relative: {part}")
        path = path / candidate

    resolved = path.resolve()
    try:
        resolved.relative_to(artifact_root)
    except ValueError as exc:
        raise SafetyError(f"Safety error: artifact path escapes artifact directory: {path}") from exc

    if create_parent:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def normalize_command(command: str) -> str:
    """Normalize command whitespace for safety comparisons."""

    return " ".join(command.strip().split())


def ensure_command_allowed(
    command: str,
    allowed_commands: list[str] | tuple[str, ...],
    forbidden_commands: list[str] | tuple[str, ...],
) -> str:
    """Validate one command against forbidden fragments and an exact allowlist."""

    if not isinstance(command, str) or not command.strip():
        raise SafetyError("Safety error: command must be a non-empty string.")

    normalized = normalize_command(command)
    lowered = normalized.lower()

    for fragment in forbidden_commands:
        normalized_fragment = normalize_command(fragment).lower()
        if normalized_fragment and normalized_fragment in lowered:
            raise SafetyError(
                f"Safety error: command contains forbidden fragment '{fragment}': {command}"
            )

    allowed = {normalize_command(item) for item in allowed_commands}
    if normalized not in allowed:
        allowed_display = ", ".join(sorted(allowed)) or "<none>"
        raise SafetyError(
            f"Safety error: command is not allowlisted: {command}. "
            f"Allowed commands: {allowed_display}."
        )

    return normalized


def validate_stage_commands(
    commands: list[str] | tuple[str, ...],
    allowed_commands: list[str] | tuple[str, ...],
    forbidden_commands: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    """Validate each command in a command stage."""

    return tuple(
        ensure_command_allowed(command, allowed_commands, forbidden_commands)
        for command in commands
    )
