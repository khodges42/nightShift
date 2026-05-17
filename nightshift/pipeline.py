"""Deterministic pipeline runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .agents import AgentExecutor
from .artifacts import ArtifactStore
from .commands import CommandExecutor
from .config import COMMAND_STAGE_TYPES, NightShiftConfig, StageConfig
from .context import ContextManager
from .errors import PipelineError
from .errors import NightShiftError
from .git import ensure_clean_worktree, write_diff_artifact, write_git_artifacts
from .reports import ReportGenerator
from .stages import StageResult
from .tasks import Task, mark_task_completed


@dataclass(frozen=True)
class PipelineResult:
    task_id: str
    status: str
    retry_count: int
    stage_results: tuple[StageResult, ...]
    artifact_dir: str
    reason: str


@dataclass(frozen=True)
class MultiTaskResult:
    status: str
    task_results: tuple[PipelineResult, ...]
    completed_count: int
    failed_count: int
    reason: str


class PipelineRunner:
    """Execute configured stages for one task."""

    def __init__(
        self,
        config: NightShiftConfig,
        artifacts: ArtifactStore | None = None,
        agent_timeout_seconds: int = 600,
        command_timeout_seconds: int = 300,
    ) -> None:
        self.config = config
        self.artifacts = artifacts or ArtifactStore.from_config(config)
        self.context = ContextManager(self.artifacts)
        self.reports = ReportGenerator(
            config.project.root,
            self.artifacts,
            experiment_label=config.experiment.label,
            prompt_variant=config.experiment.prompt_variant,
        )
        self.agent_executor = AgentExecutor(
            config.project.root,
            config.agents,
            self.artifacts,
            timeout_seconds=agent_timeout_seconds,
        )
        self.command_executor = CommandExecutor(
            config.project.root,
            config.safety,
            self.artifacts,
            timeout_seconds=command_timeout_seconds,
        )

    def run_task(self, task: Task) -> PipelineResult:
        ensure_clean_worktree(self.config.project.root, self.config.safety.require_clean_worktree)
        self.artifacts.initialize_run()
        self.artifacts.write_config_snapshot(self.config.path)
        self.artifacts.write_prompt_snapshots(
            {
                agent_id: self.config.project.root / agent.system_prompt
                for agent_id, agent in self.config.agents.items()
            }
        )
        self.artifacts.write_run_metadata(format_run_metadata(self.config))
        self.artifacts.write_task_snapshot(task)
        write_git_artifacts(self.artifacts, task.id, "before")
        self.context.ensure_project_context()
        self.context.create_task_context(task)

        stages = list(self.config.pipeline.stages)
        stage_indexes = {stage.id: index for index, stage in enumerate(stages)}
        stage_results: list[StageResult] = []
        previous_outputs: dict[str, str] = {}
        retry_notes: list[str] = []
        retry_count = 0
        index = 0
        final_status = "complete"
        final_reason = "Pipeline completed."

        while index < len(stages):
            stage = stages[index]
            try:
                result = self._run_stage(stage, task, previous_outputs, retry_notes)
            except NightShiftError as exc:
                result = StageResult(
                    stage_id=stage.id,
                    status="fail",
                    reason=str(exc),
                )
            except OSError as exc:
                result = StageResult(
                    stage_id=stage.id,
                    status="fail",
                    reason=f"Unexpected OS error while running stage: {exc}",
                )
            stage_results.append(result)
            previous_outputs[stage.id] = self._read_output(result.output_path)
            if result.context_update:
                retry_notes.append(f"Context update from '{stage.id}': {result.context_update}")

            if result.status == "pass":
                index += 1
                continue

            target_stage = stage.on_fail or result.next_stage
            if target_stage:
                if retry_count >= self.config.pipeline.max_task_retries:
                    final_status = "failed"
                    final_reason = (
                        f"Retry limit reached after stage '{stage.id}': {result.reason}"
                    )
                    break
                if target_stage not in stage_indexes:
                    final_status = "failed"
                    final_reason = (
                        f"Stage '{stage.id}' requested unknown next stage '{target_stage}'."
                    )
                    break
                retry_count += 1
                retry_notes.append(
                    f"Retry {retry_count}: stage '{stage.id}' returned "
                    f"{result.status} ({result.reason}); redirecting to '{target_stage}'."
                )
                index = stage_indexes[target_stage]
                continue

            final_status = "failed"
            final_reason = f"Stage '{stage.id}' returned {result.status}: {result.reason}"
            break

        context_out_path = self.context.write_context_out(
            task,
            final_status,
            final_reason,
            retry_notes,
            durable_notes=[
                result.context_update
                for result in stage_results
                if result.context_update
            ],
        )
        completion_changed = False
        if final_status == "complete":
            completion_changed = mark_task_completed(
                self.config.project.root,
                self.config.project.task_file,
                task.id,
            )
        self.artifacts.write_stage_output(
            task.id,
            "task-completion.md",
            format_task_completion(task, final_status, completion_changed),
        )
        write_git_artifacts(self.artifacts, task.id, "after")
        write_diff_artifact(self.artifacts, task.id)
        self.reports.write_reports(
            task,
            final_status,
            final_reason,
            retry_count,
            stage_results,
            context_out_path=context_out_path,
        )

        return PipelineResult(
            task_id=task.id,
            status=final_status,
            retry_count=retry_count,
            stage_results=tuple(stage_results),
            artifact_dir=str(self.artifacts.create_task_dir(task.id).directory.relative_to(self.config.project.root)),
            reason=final_reason,
        )

    def run_tasks(self, tasks: list[Task] | tuple[Task, ...]) -> MultiTaskResult:
        self.artifacts.initialize_run()
        results: list[PipelineResult] = []
        known_ids = {task.id for task in tasks}
        completed_ids = {task.id for task in tasks if task.completed}
        for task in tasks:
            if task.completed:
                continue
            missing_refs = [dependency for dependency in task.dependencies if dependency not in known_ids]
            incomplete_deps = [
                dependency for dependency in task.dependencies if dependency in known_ids and dependency not in completed_ids
            ]
            if missing_refs or incomplete_deps:
                reason_parts = []
                if missing_refs:
                    reason_parts.append(f"missing dependencies: {', '.join(missing_refs)}")
                if incomplete_deps:
                    reason_parts.append(f"incomplete dependencies: {', '.join(incomplete_deps)}")
                blocked = PipelineResult(
                    task_id=task.id,
                    status="blocked",
                    retry_count=0,
                    stage_results=(),
                    artifact_dir="",
                    reason="Task blocked by " + "; ".join(reason_parts),
                )
                results.append(blocked)
                if not self.config.pipeline.continue_on_task_failure:
                    break
                continue
            result = self.run_task(task)
            results.append(result)
            if result.status == "complete":
                completed_ids.add(task.id)
            if result.status != "complete" and not self.config.pipeline.continue_on_task_failure:
                break

        completed_count = sum(1 for result in results if result.status == "complete")
        failed_count = sum(1 for result in results if result.status != "complete")
        status = "complete" if failed_count == 0 else "failed"
        reason = "All selected tasks completed." if status == "complete" else "One or more tasks failed."
        self.artifacts.run_summary_path.write_text(
            format_aggregate_run_summary(results, status, reason),
            encoding="utf-8",
        )
        return MultiTaskResult(
            status=status,
            task_results=tuple(results),
            completed_count=completed_count,
            failed_count=failed_count,
            reason=reason,
        )

    def _run_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str],
        retry_notes: list[str],
    ) -> StageResult:
        if stage.type in {"agent", "agent_review", "review"}:
            context = self.context.read_context(task, retry_notes)
            return self.agent_executor.run_stage(
                stage,
                task,
                previous_outputs,
                retry_notes,
                project_context=context.project_context,
                task_context=context.task_context,
                retry_context=context.retry_context,
            )
        if stage.type in COMMAND_STAGE_TYPES:
            return self.command_executor.run_stage(stage, task.id)
        if stage.type == "summarize":
            output_path = self.artifacts.write_stage_output(
                task.id,
                stage.output or "final-notes.md",
                format_summary_stage(task, previous_outputs, retry_notes),
            )
            return StageResult(
                stage_id=stage.id,
                status="pass",
                reason="Summary written.",
                output_path=str(output_path.relative_to(self.config.project.root)),
            )
        raise PipelineError(f"Pipeline error: unsupported stage type '{stage.type}'.")

    def _read_output(self, output_path: str | None) -> str:
        if output_path is None:
            return ""
        path = self.config.project.root / Path(output_path)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

def format_summary_stage(
    task: Task,
    previous_outputs: dict[str, str],
    retry_notes: list[str],
) -> str:
    outputs = "\n".join(f"- {stage_id}" for stage_id in previous_outputs)
    retries = "\n".join(f"- {note}" for note in retry_notes) or "- None"
    return "\n".join(
        [
            "# Final Notes",
            "",
            f"Task: `{task.id}`",
            f"Title: {task.title}",
            "",
            "## Stage Outputs",
            "",
            outputs or "- None",
            "",
            "## Retry Notes",
            "",
            retries,
            "",
        ]
    )


def format_task_completion(task: Task, status: str, changed: bool) -> str:
    return "\n".join(
        [
            "# Task Completion",
            "",
            f"Task: `{task.id}`",
            f"Pipeline status: {status}",
            f"Marked complete: {str(changed).lower()}",
            "",
        ]
    )


def format_aggregate_run_summary(results: list[PipelineResult], status: str, reason: str) -> str:
    lines = [
        "# Run Summary",
        "",
        f"Status: {status}",
        f"Reason: {reason}",
        f"Tasks run: {len(results)}",
        f"Completed tasks: {sum(1 for result in results if result.status == 'complete')}",
        f"Failed tasks: {sum(1 for result in results if result.status != 'complete')}",
        "",
        "## Tasks",
        "",
    ]
    if not results:
        lines.append("- None")
    for result in results:
        lines.append(
            f"- `{result.task_id}`: {result.status} "
            f"(retries: {result.retry_count}) - {result.reason}"
        )
    lines.append("")
    return "\n".join(lines)


def format_run_metadata(config: NightShiftConfig) -> str:
    lines = [
        "# Run Metadata",
        "",
        f"Project: {config.project.name}",
        f"Experiment label: {config.experiment.label or ''}",
        f"Prompt variant: {config.experiment.prompt_variant or ''}",
        "",
        "## Agents",
        "",
    ]
    for agent in config.agents.values():
        lines.extend(
            [
                f"### {agent.id}",
                "",
                f"- Backend: {agent.backend}",
                f"- Model: {agent.model or ''}",
                f"- Command: {agent.command or ''}",
                f"- System prompt: {agent.system_prompt}",
                "",
            ]
        )
    return "\n".join(lines)
