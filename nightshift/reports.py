"""Human-readable NightShift reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from .artifacts import ArtifactStore
from .stages import StageResult
from .tasks import Task


@dataclass(frozen=True)
class TaskReport:
    final_notes_path: Path
    stage_results_path: Path
    run_summary_path: Path
    devlog_path: Path


class ReportGenerator:
    """Write task and run summaries from pipeline results."""

    def __init__(
        self,
        project_root: Path,
        artifacts: ArtifactStore,
        experiment_label: str | None = None,
        prompt_variant: str | None = None,
    ) -> None:
        self.project_root = project_root
        self.artifacts = artifacts
        self.experiment_label = experiment_label
        self.prompt_variant = prompt_variant

    def write_reports(
        self,
        task: Task,
        status: str,
        reason: str,
        retry_count: int,
        stage_results: list[StageResult],
        context_out_path: Path | None = None,
    ) -> TaskReport:
        modified_files = collect_modified_files(self.project_root)
        stage_results_path = self.artifacts.write_stage_output(
            task.id,
            "stage-results.md",
            format_stage_results(task, status, reason, retry_count, stage_results),
        )
        artifact_index_path = self.artifacts.write_stage_output(
            task.id,
            "artifact-index.md",
            format_artifact_index(self.artifacts.create_task_dir(task.id).directory),
        )
        final_notes_path = self.artifacts.write_final_task_notes(
            task.id,
            format_task_report(
                task=task,
                status=status,
                reason=reason,
                retry_count=retry_count,
                stage_results=stage_results,
                modified_files=modified_files,
                stage_results_path=stage_results_path,
                context_out_path=context_out_path,
                artifact_index_path=artifact_index_path,
                experiment_label=self.experiment_label,
                prompt_variant=self.prompt_variant,
            ),
        )
        self.artifacts.run_summary_path.write_text(
            format_run_summary(
                task=task,
                status=status,
                reason=reason,
                retry_count=retry_count,
                modified_files=modified_files,
                final_notes_path=final_notes_path,
                stage_results_path=stage_results_path,
                experiment_label=self.experiment_label,
                prompt_variant=self.prompt_variant,
            ),
            encoding="utf-8",
        )
        devlog_path = self.artifacts.run_dir / "devlog.md"
        devlog_path.write_text(
            format_devlog(
                task=task,
                status=status,
                reason=reason,
                retry_count=retry_count,
                stage_results=stage_results,
                modified_files=modified_files,
                run_log=self.artifacts.run_log_path.read_text(encoding="utf-8", errors="replace")
                if self.artifacts.run_log_path.exists()
                else "",
            ),
            encoding="utf-8",
        )
        return TaskReport(final_notes_path, stage_results_path, self.artifacts.run_summary_path, devlog_path)


def format_stage_results(
    task: Task,
    status: str,
    reason: str,
    retry_count: int,
    stage_results: list[StageResult],
) -> str:
    lines = [
        "# Stage Results",
        "",
        f"Task: `{task.id}`",
        f"Status: {status}",
        f"Retry count: {retry_count}",
        f"Reason: {reason}",
        "",
    ]
    for result in stage_results:
        lines.extend(
            [
                f"## {result.stage_id}",
                "",
                f"Status: {result.status}",
                f"Reason: {result.reason}",
                f"Output: {result.output_path or ''}",
                f"Next stage: {result.next_stage or ''}",
                f"Context update: {result.context_update or ''}",
                "",
            ]
        )
    return "\n".join(lines)


def format_task_report(
    task: Task,
    status: str,
    reason: str,
    retry_count: int,
    stage_results: list[StageResult],
    modified_files: list[str],
    stage_results_path: Path,
    context_out_path: Path | None,
    artifact_index_path: Path | None,
    experiment_label: str | None = None,
    prompt_variant: str | None = None,
) -> str:
    stage_lines = "\n".join(
        f"- `{result.stage_id}`: {result.status} ({result.reason})" for result in stage_results
    )
    artifact_lines = [
        f"- Stage results: `{stage_results_path.name}`",
    ]
    if context_out_path is not None:
        artifact_lines.append(f"- Context out: `{context_out_path.name}`")
    if artifact_index_path is not None:
        artifact_lines.append(f"- Artifact index: `{artifact_index_path.name}`")
    modified = "\n".join(f"- `{path}`" for path in modified_files) if modified_files else "- Unavailable or none detected"

    return "\n".join(
        [
            "# Final Task Notes",
            "",
            f"Task: `{task.id}`",
            f"Title: {task.title}",
            f"Status: {status}",
            f"Retry count: {retry_count}",
            f"Reason: {reason}",
            "",
            "## Experiment",
            "",
            f"- Label: {experiment_label or ''}",
            f"- Prompt variant: {prompt_variant or ''}",
            "",
            "## Acceptance Criteria",
            "",
            "\n".join(f"- {item}" for item in task.acceptance_criteria),
            "",
            "## Stage Results",
            "",
            stage_lines or "- None",
            "",
            "## Modified Files",
            "",
            modified,
            "",
            "## Artifacts",
            "",
            "\n".join(artifact_lines),
            "",
        ]
    )


def format_artifact_index(task_dir: Path) -> str:
    groups: dict[str, list[str]] = {
        "Core": [],
        "Patch Flow": [],
        "Diagnostics": [],
        "Retries": [],
        "Resources": [],
        "Other": [],
    }
    for path in sorted(item for item in task_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(task_dir).as_posix()
        target = "Other"
        if relative in {"task.md", "context.md", "context-out.md", "stage-results.md", "task-completion.md", "final-notes.md"}:
            target = "Core"
        elif relative.endswith(".patch") or "patch-" in relative or "normalized" in relative:
            target = "Patch Flow"
        elif relative.startswith("diagnostics/") or "failure" in relative:
            target = "Diagnostics"
        elif relative.startswith("retries/") or "retry" in relative or "repair" in relative:
            target = "Retries"
        elif relative.startswith("resources/") or relative == "resource-requests.md":
            target = "Resources"
        groups[target].append(relative)
    lines = ["# Artifact Index", ""]
    for name, paths in groups.items():
        lines.extend([f"## {name}", ""])
        lines.extend(f"- `{path}`" for path in paths) if paths else lines.append("- None")
        lines.append("")
    return "\n".join(lines)


def format_run_summary(
    task: Task,
    status: str,
    reason: str,
    retry_count: int,
    modified_files: list[str],
    final_notes_path: Path,
    stage_results_path: Path,
    experiment_label: str | None = None,
    prompt_variant: str | None = None,
) -> str:
    modified = "\n".join(f"- `{path}`" for path in modified_files) if modified_files else "- Unavailable or none detected"
    return "\n".join(
        [
            "# Run Summary",
            "",
            f"- Task: {task.id}",
            f"- Status: {status}",
            f"- Retry count: {retry_count}",
            f"- Reason: {reason}",
            f"- Experiment label: {experiment_label or ''}",
            f"- Prompt variant: {prompt_variant or ''}",
            "",
            "## Modified Files",
            "",
            modified,
            "",
            "## Artifacts",
            "",
            f"- Final notes: `{final_notes_path.relative_to(final_notes_path.parents[2])}`",
            f"- Stage results: `{stage_results_path.relative_to(stage_results_path.parents[2])}`",
            "",
        ]
    )


def format_devlog(
    task: Task,
    status: str,
    reason: str,
    retry_count: int,
    stage_results: list[StageResult],
    modified_files: list[str],
    run_log: str = "",
) -> str:
    lines = [
        "# Devlog",
        "",
        f"Task `{task.id}`: {task.title}",
        "",
        f"Status: {status.upper()}",
        f"Retries: {retry_count}",
        f"Outcome: {reason}",
        "",
    ]
    timeline = _format_devlog_timeline(run_log)
    if timeline:
        lines.extend(["## Timeline", "", *timeline, ""])
    stage_titles = {
        "agent": "Agent",
        "agent_review": "Reviewer",
        "code_writer": "Implementer",
        "file_writer": "Implementer",
        "patch_normalizer": "Normalizer",
        "patch_validator": "Patch validator",
        "patch_apply": "Patch apply",
        "command": "Command",
        "repo_context": "Context builder",
        "summarize": "Summarizer",
    }
    for result in stage_results:
        label = _devlog_stage_label(result.stage_id, stage_titles)
        verb = _devlog_verb(label, result.status)
        lines.extend(
            [
                f"## {label}",
                "",
                f"{verb}:",
                f"- Status: {result.status}",
                f"- Reason: {result.reason}",
            ]
        )
        if result.output_path:
            lines.append(f"- Artifact: `{result.output_path}`")
        if result.context_update:
            lines.append(f"- Note: {result.context_update}")
        lines.append("")
    lines.extend(
        [
            "## Modified Files",
            "",
            *([f"- `{path}`" for path in modified_files] if modified_files else ["- None detected"]),
            "",
        ]
    )
    return "\n".join(lines)


def _format_devlog_timeline(run_log: str) -> list[str]:
    current_stage = ""
    lines: list[str] = []
    for raw_line in run_log.splitlines():
        event, fields = _parse_run_log_line(raw_line)
        if not event:
            continue
        stage_id = fields.get("stage_id") or current_stage
        if event == "stage.start":
            current_stage = fields.get("stage_id", current_stage)
            lines.append(f"- {stage_id}: started {fields.get('stage_type', 'stage')}.")
        elif event == "agent.rerun":
            lines.append(f"- {stage_id}: reran the agent with extra context.")
        elif event == "tool.call":
            actor = _devlog_stage_label(stage_id or current_stage or "repo lookup", {})
            tool = fields.get("tool", "tool")
            path = fields.get("path", ".")
            pattern = fields.get("pattern")
            if tool == "grep":
                lines.append(f"- {actor}: searched `{path}` for `{pattern or ''}`.")
            elif tool == "read_file":
                lines.append(f"- {actor}: read `{path}`.")
            elif tool == "list_files":
                lines.append(f"- {actor}: listed files under `{path}`.")
            else:
                lines.append(f"- {actor}: ran repo lookup `{tool}` on `{path}`.")
        elif event == "artifact.write":
            artifact = fields.get("artifact_path")
            if artifact:
                actor = _devlog_stage_label(stage_id or current_stage or "artifact", {})
                lines.append(f"- {actor}: wrote `{artifact}`.")
        elif event == "command.start":
            lines.append(f"- {stage_id}: ran `{fields.get('command', 'command')}`.")
        elif event == "command.finish":
            lines.append(f"- {stage_id}: command exited with code {fields.get('exit_code', '?')}.")
        elif event == "stage.next":
            lines.append(f"- {stage_id}: skipped ahead to `{fields.get('next_stage', '')}`.")
        elif event == "stage.retry":
            lines.append(f"- {stage_id}: requested retry to `{fields.get('next_stage', '')}`.")
        elif event == "stage.finish":
            lines.append(f"- {stage_id}: finished with {fields.get('status', 'unknown')} - {fields.get('reason', '')}")
    return lines


def _parse_run_log_line(line: str) -> tuple[str, dict[str, str]]:
    parts = [part.strip() for part in line.split(" | ")]
    if len(parts) < 3:
        return "", {}
    event = parts[1]
    fields: dict[str, str] = {}
    for part in parts[3:]:
        match = re.match(r"([^=]+)=(.*)", part)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return event, fields


def _devlog_stage_label(stage_id: str, stage_titles: dict[str, str]) -> str:
    normalized = stage_id.lower()
    if "plan" in normalized:
        return "Planner"
    if "implement" in normalized or "write" in normalized:
        return "Implementer"
    if "review" in normalized:
        return "Reviewer"
    if "test" in normalized:
        return "Tests"
    if "context" in normalized:
        return "Context builder"
    if "validate" in normalized:
        return "Patch validator"
    if "apply" in normalized:
        return "Patch apply"
    if "normalize" in normalized:
        return "Normalizer"
    return stage_titles.get(normalized, stage_id.replace("_", " ").title())


def _devlog_verb(label: str, status: str) -> str:
    if label == "Planner":
        return "Planner proposed"
    if label == "Implementer":
        return "Implementer tried"
    if label == "Reviewer":
        return "Reviewer responded"
    if label == "Tests":
        return "Tests reported"
    if status == "fail":
        return f"{label} stopped"
    return f"{label} completed"


def collect_modified_files(project_root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            "git status --short",
            cwd=project_root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []

    files: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip())
    return files
