"""Scoped repository lookup tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fnmatch
import re

from .artifacts import ArtifactStore
from .config import SafetyConfig
from .errors import SafetyError
from .runlog import NullRunLogger, RunLogger
from .safety import resolve_inside_root, resolve_project_root, validate_scoped_paths


DEFAULT_MAX_BYTES = 20_000
DEFAULT_MAX_MATCHES = 100


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, str]
    output: str


class RepoTools:
    """Read-only repo tools constrained to configured project scope."""

    def __init__(
        self,
        project_root: str | Path,
        safety: SafetyConfig,
        artifacts: ArtifactStore,
        logger: RunLogger | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.safety = safety
        self.artifacts = artifacts
        self.logger = logger or NullRunLogger()
        self.scoped_roots = validate_scoped_paths(
            self.project_root,
            safety.scoped_paths or (".",),
        )

    def list_files(self, path: str = ".", pattern: str = "*", max_files: int = 200) -> str:
        root = self._resolve_scoped(path, "list_files path")
        if not root.exists():
            return f"Path not found: {path}"
        if root.is_file():
            candidates = [root]
        else:
            candidates = [item for item in root.rglob("*") if item.is_file()]
        relative_files = [
            _relative(item, self.project_root)
            for item in sorted(candidates)
            if fnmatch.fnmatch(item.name, pattern)
        ]
        lines = relative_files[:max_files]
        if len(relative_files) > max_files:
            lines.append(f"... truncated {len(relative_files) - max_files} files")
        return "\n".join(lines) or "No files found."

    def read_file(self, path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
        file_path = self._resolve_scoped(path, "read_file path")
        if not file_path.exists() or not file_path.is_file():
            return f"File not found: {path}"
        data = file_path.read_bytes()[:max_bytes + 1]
        truncated = len(data) > max_bytes
        text = data[:max_bytes].decode("utf-8", errors="replace")
        numbered = _line_number(text)
        if truncated:
            numbered += "\n... truncated"
        return numbered

    def grep(
        self,
        pattern: str,
        path: str = ".",
        max_matches: int = DEFAULT_MAX_MATCHES,
    ) -> str:
        root = self._resolve_scoped(path, "grep path")
        regex = re.compile(pattern)
        files = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        matches: list[str] = []
        for file_path in sorted(files):
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    matches.append(f"{_relative(file_path, self.project_root)}:{line_number}: {line}")
                    if len(matches) >= max_matches:
                        matches.append("... truncated")
                        return "\n".join(matches)
        return "\n".join(matches) or "No matches found."

    def write_tool_artifact(self, task_id: str, calls: list[ToolCall], filename: str = "repo-tools.md") -> Path:
        content = format_tool_calls(calls)
        path = self.artifacts.write_stage_output(task_id, filename, content)
        self.logger.event(
            "artifact.write",
            "Wrote repo tool artifact",
            task_id=task_id,
            artifact_path=path.relative_to(self.project_root),
        )
        return path

    def execute_requests(self, task_id: str, requests: list[ToolCall], filename: str = "repo-tools.md") -> str:
        completed: list[ToolCall] = []
        for request in requests:
            self.logger.event(
                "tool.call",
                "Running repo lookup tool",
                task_id=task_id,
                tool=request.name,
                **request.arguments,
            )
            try:
                output = self._execute_request(request)
            except (SafetyError, re.error) as exc:
                output = str(exc)
            completed.append(ToolCall(request.name, request.arguments, output))
        self.write_tool_artifact(task_id, completed, filename=filename)
        return format_tool_calls(completed)

    def _execute_request(self, request: ToolCall) -> str:
        if request.name == "list_files":
            return self.list_files(
                path=request.arguments.get("path", "."),
                pattern=request.arguments.get("pattern", "*"),
            )
        if request.name == "read_file":
            path = request.arguments.get("path")
            if not path:
                return "Missing required argument: path"
            return self.read_file(path)
        if request.name == "grep":
            pattern = request.arguments.get("pattern")
            if not pattern:
                return "Missing required argument: pattern"
            return self.grep(pattern, path=request.arguments.get("path", "."))
        return f"Unsupported repo lookup tool: {request.name}"

    def _resolve_scoped(self, path: str, context: str) -> Path:
        resolved = resolve_inside_root(self.project_root, path, context)
        for scoped_root in self.scoped_roots:
            try:
                resolved.relative_to(scoped_root)
                return resolved
            except ValueError:
                continue
        scopes = ", ".join(_relative(item, self.project_root) for item in self.scoped_roots)
        raise SafetyError(f"Safety error: {context} is outside configured scoped paths: {path}. Scopes: {scopes}")


def format_tool_calls(calls: list[ToolCall]) -> str:
    lines = ["# Repo Tool Calls", ""]
    if not calls:
        lines.append("No tool calls.")
        return "\n".join(lines)
    for index, call in enumerate(calls, start=1):
        lines.extend(
            [
                f"## {index}. {call.name}",
                "",
                "Arguments:",
            ]
        )
        for key, value in sorted(call.arguments.items()):
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "Output:", "", "```text", call.output.rstrip(), "```", ""])
    return "\n".join(lines)


def parse_lookup_requests(text: str) -> list[ToolCall]:
    """Parse a small YAML-like lookup request list from model output."""

    lines = text.splitlines()
    in_section = False
    current: dict[str, str] = {}
    requests: list[ToolCall] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        name = current.pop("tool", "").strip()
        if name:
            requests.append(ToolCall(name=name, arguments=dict(current), output=""))
        current = {}

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped in {"lookup_requests:", "repo_lookup:", "repo_lookups:"}:
            in_section = True
            continue
        if not in_section:
            continue
        if not stripped:
            continue
        if not raw_line.startswith((" ", "-", "\t")) and not stripped.endswith(":"):
            break
        if stripped.startswith("- "):
            flush()
            stripped = stripped[2:].strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "tool" and current:
            flush()
        current[key] = value
    flush()
    return requests


def extract_agent_stdout(artifact_text: str) -> str:
    lines = artifact_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "## stdout":
            continue
        end = next(
            (cursor for cursor in range(index + 1, len(lines)) if lines[cursor].strip() == "## stderr"),
            len(lines),
        )
        section = lines[index + 1:end]
        while section and not section[0].strip():
            section = section[1:]
        while section and not section[-1].strip():
            section = section[:-1]
        if section and section[0].strip().startswith("```"):
            section = section[1:]
        if section and section[-1].strip() == "```":
            section = section[:-1]
        return "\n".join(section)
    return artifact_text


def _line_number(text: str) -> str:
    return "\n".join(f"{index}: {line}" for index, line in enumerate(text.splitlines(), start=1))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
