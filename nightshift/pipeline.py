"""Deterministic pipeline runner."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import subprocess

from .agents import AgentExecutor
from .artifacts import ArtifactStore
from .commands import CommandExecutor, extract_test_file_paths, render_command_template
from .config import COMMAND_STAGE_TYPES, NightShiftConfig, StageConfig
from .context import ContextManager
from .dependencies import diagnose_python_dependencies, format_dependency_diagnostic
from .escalation import evaluate_retry_churn, format_escalation_decision
from .errors import PipelineError
from .errors import NightShiftError
from .failures import build_failure_signature, classify_failure, format_failure_classification
from .git import ensure_clean_worktree, write_diff_artifact, write_git_artifacts
from .patches import (
    DEFAULT_FORBIDDEN_PATHS,
    DEFAULT_MAX_CHANGED_LINES,
    DEFAULT_MAX_FILES,
    FileUpdate,
    apply_patch_with_git,
    extract_unified_diff,
    format_patch_apply_result,
    format_validation_result,
    generate_patch_from_file_updates,
    normalize_patch_text,
    parse_file_updates,
    validate_patch,
)
from .project_chart import build_project_context_chart
from .reports import ReportGenerator
from .repo_tools import RepoTools, extract_agent_stdout, parse_lookup_requests
from .resources import format_resource_report, parse_resource_requests, satisfy_resource_requests
from .retry_memory import RetryMemoryEntry, entry_from_stage, summarize_retry_memory
from .semantic_index import (
    build_semantic_index,
    format_search_results,
    format_semantic_index,
    search_index,
)
from .runlog import RunLogger
from .stages import StageResult
from .tasks import Task, mark_task_completed
from .telemetry import TelemetryEntry, format_telemetry_summary, telemetry_from_stage_output


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
        logger: RunLogger | None = None,
    ) -> None:
        self.config = config
        self.artifacts = artifacts or ArtifactStore.from_config(config)
        self.logger = logger or RunLogger()
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
            logger=self.logger,
        )
        self.command_executor = CommandExecutor(
            config.project.root,
            config.safety,
            self.artifacts,
            timeout_seconds=command_timeout_seconds,
            logger=self.logger,
        )
        self.repo_tools = RepoTools(
            config.project.root,
            config.safety,
            self.artifacts,
            logger=self.logger,
        )

    def run_task(self, task: Task) -> PipelineResult:
        ensure_clean_worktree(self.config.project.root, self.config.safety.require_clean_worktree)
        self.artifacts.initialize_run()
        self.logger.bind(self.artifacts)
        self.logger.event(
            "task.start",
            "Starting task",
            run_id=self.artifacts.run_id,
            task_id=task.id,
            task_title=task.title,
        )
        self.artifacts.write_config_snapshot(self.config.path)
        self.artifacts.write_prompt_snapshots(
            {
                agent_id: self.config.project.root / agent.system_prompt
                for agent_id, agent in self.config.agents.items()
            }
        )
        self.artifacts.write_run_metadata(format_run_metadata(self.config))
        self.artifacts.write_task_snapshot(task)
        self._write_project_context_chart()
        write_git_artifacts(self.artifacts, task.id, "before")
        self.context.ensure_project_context()
        self.context.create_task_context(task)

        stages = list(self.config.pipeline.stages)
        stage_indexes = {stage.id: index for index, stage in enumerate(stages)}
        stage_results: list[StageResult] = []
        previous_outputs: dict[str, str] = {}
        retry_notes: list[str] = []
        retry_memory: list[RetryMemoryEntry] = []
        telemetry_entries: list[TelemetryEntry] = []
        retry_count = 0
        index = 0
        final_status = "complete"
        final_reason = "Pipeline completed."
        preflight_result = self._preflight_task(task, stages)
        if preflight_result:
            stage_results.append(preflight_result)
            final_status = "failed"
            final_reason = preflight_result.reason
            index = len(stages)

        while index < len(stages):
            stage = stages[index]
            self.logger.event(
                "stage.start",
                "Starting stage",
                run_id=self.artifacts.run_id,
                task_id=task.id,
                stage_id=stage.id,
                stage_type=stage.type,
                retry_count=retry_count,
            )
            try:
                result = self._run_stage(stage, task, previous_outputs, retry_notes, retry_count)
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
            if stage.id in previous_outputs:
                del previous_outputs[stage.id]
            previous_outputs[stage.id] = self._read_output(result.output_path)
            telemetry_entries.append(self._telemetry_entry(stage, result, retry_count))
            self._write_telemetry(task.id, telemetry_entries)
            self.logger.event(
                "stage.finish",
                "Finished stage",
                run_id=self.artifacts.run_id,
                task_id=task.id,
                stage_id=stage.id,
                status=result.status,
                reason=result.reason,
                artifact_path=result.output_path,
            )
            if result.context_update:
                retry_notes.append(f"Context update from '{stage.id}': {result.context_update}")

            if result.status == "pass":
                if stage.type in {"agent_review", "review"} and result.next_stage:
                    self.logger.event(
                        "stage.next_ignored",
                        "Ignoring next_stage from passing review",
                        run_id=self.artifacts.run_id,
                        task_id=task.id,
                        stage_id=stage.id,
                        requested_next_stage=result.next_stage,
                    )
                    index += 1
                    continue
                if result.next_stage:
                    if result.next_stage not in stage_indexes:
                        final_status = "failed"
                        final_reason = (
                            f"Stage '{stage.id}' requested unknown next stage '{result.next_stage}'."
                        )
                        break
                    self.logger.event(
                        "stage.next",
                        "Jumping to requested next stage",
                        run_id=self.artifacts.run_id,
                        task_id=task.id,
                        stage_id=stage.id,
                        next_stage=result.next_stage,
                    )
                    index = stage_indexes[result.next_stage]
                    continue
                index += 1
                continue

            target_stage = stage.on_fail or result.next_stage
            analysis_note = self._write_failure_diagnostics(stage, task, result, retry_count)
            if analysis_note:
                retry_notes.append(analysis_note)
            debugger_note = self._run_debugger_if_configured(task, result, retry_notes)
            if debugger_note:
                retry_notes.append(debugger_note)
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
                output = self._read_output(result.output_path)
                failure_signature = ""
                if stage.type in COMMAND_STAGE_TYPES:
                    failure_signature = build_failure_signature(output, result.reason)
                memory_entry = entry_from_stage(
                    retry_count,
                    result,
                    target_stage,
                    failure_signature=failure_signature,
                )
                retry_memory.append(memory_entry)
                self.artifacts.write_stage_output(
                    task.id,
                    "retry-memory.md",
                    summarize_retry_memory(tuple(retry_memory)),
                )
                if _repeated_protected_path_violation(tuple(retry_memory)):
                    final_status = "failed"
                    final_reason = (
                        "Escalation policy stopped retries: implementation repeatedly "
                        "attempted to modify paths outside the stage allowlist."
                    )
                    break
                decision = evaluate_retry_churn(
                    tuple(retry_memory),
                    retry_budget=self.config.pipeline.max_task_retries + 1,
                    repeated_signature_after=self.config.pipeline.stop_on_repeated_failure_signature_after,
                )
                self.artifacts.write_stage_output(
                    task.id,
                    "escalation-policy.md",
                    format_escalation_decision(decision),
                )
                if decision.should_stop:
                    final_status = "failed"
                    final_reason = f"Escalation policy stopped retries: {decision.reason}"
                    break
                self.logger.event(
                    "stage.retry",
                    "Redirecting after stage result",
                    run_id=self.artifacts.run_id,
                    task_id=task.id,
                    stage_id=stage.id,
                    status=result.status,
                    retry_count=retry_count,
                    next_stage=target_stage,
                )
                retry_notes.append(self._format_retry_note(retry_count, stage, result, target_stage))
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
        self._write_telemetry(task.id, telemetry_entries)
        self.logger.event(
            "task.finish",
            "Finished task",
            run_id=self.artifacts.run_id,
            task_id=task.id,
            status=final_status,
            retry_count=retry_count,
            reason=final_reason,
            artifact_path=self.artifacts.create_task_dir(task.id).directory.relative_to(self.config.project.root),
        )

        return PipelineResult(
            task_id=task.id,
            status=final_status,
            retry_count=retry_count,
            stage_results=tuple(stage_results),
            artifact_dir=str(self.artifacts.create_task_dir(task.id).directory.relative_to(self.config.project.root)),
            reason=final_reason,
        )

    def _preflight_task(self, task: Task, stages: list[StageConfig]) -> StageResult | None:
        missing_paths: list[str] = []
        for stage in stages:
            if stage.type not in COMMAND_STAGE_TYPES:
                continue
            for command in stage.commands:
                rendered = render_command_template(command, task.id)
                for path_text in extract_test_file_paths(rendered):
                    if not (self.config.project.root / path_text).exists():
                        missing_paths.append(path_text)
        if not missing_paths:
            return None
        unique_paths = tuple(dict.fromkeys(missing_paths))
        details = "\n".join(f"- `{path}`" for path in unique_paths)
        output_path = self.artifacts.write_stage_output(
            task.id,
            "preflight.md",
            "\n".join(
                [
                    "# Task Preflight",
                    "",
                    "Status: fail",
                    "Reason: configured task test file is missing.",
                    "",
                    "## Missing Files",
                    "",
                    details,
                    "",
                ]
            ),
        )
        return StageResult(
            "preflight",
            "fail",
            "Task preflight failed: configured task test file is missing: "
            + ", ".join(unique_paths),
            output_path=str(output_path.relative_to(self.config.project.root)),
        )

    def run_tasks(self, tasks: list[Task] | tuple[Task, ...]) -> MultiTaskResult:
        self.artifacts.initialize_run()
        self.logger.bind(self.artifacts)
        self.logger.event("run.start", "Starting multi-task run", run_id=self.artifacts.run_id)
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
                self.logger.event(
                    "task.blocked",
                    "Task blocked by dependencies",
                    run_id=self.artifacts.run_id,
                    task_id=task.id,
                    reason=blocked.reason,
                )
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
        self.logger.event(
            "run.finish",
            "Finished multi-task run",
            run_id=self.artifacts.run_id,
            status=status,
            completed_count=completed_count,
            failed_count=failed_count,
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
        retry_count: int = 0,
    ) -> StageResult:
        if stage.type in {"agent", "agent_review", "review"}:
            context = self.context.read_context(task, retry_notes)
            result = self.agent_executor.run_stage(
                self._stage_for_retry_agent(stage, retry_count),
                task,
                previous_outputs,
                retry_notes,
                project_context=context.project_context,
                task_context=context.task_context,
                retry_context=context.retry_context,
            )
            if stage.type == "agent":
                resource_result = self._maybe_satisfy_resource_request(stage, task, result)
                if resource_result is not None:
                    return resource_result
                return self._maybe_rerun_agent_with_repo_lookup(
                    stage,
                    task,
                    result,
                    previous_outputs,
                    retry_notes,
                    context.project_context,
                    context.task_context,
                    context.retry_context,
                )
            return result
        if stage.type in COMMAND_STAGE_TYPES:
            return self.command_executor.run_stage(_stage_with_attempt_output(stage, retry_count), task.id)
        if stage.type == "code_writer":
            return self._run_code_writer_stage(stage, task, previous_outputs, retry_notes, retry_count)
        if stage.type == "file_writer":
            return self._run_file_writer_stage(stage, task, previous_outputs, retry_notes, retry_count)
        if stage.type == "patch_normalizer":
            return self._run_patch_normalizer_stage(stage, task, previous_outputs, retry_notes, retry_count)
        if stage.type == "patch_validator":
            return self._run_patch_validator_stage(stage, task, previous_outputs, retry_count)
        if stage.type == "patch_apply":
            return self._run_patch_apply_stage(stage, task, previous_outputs, retry_count)
        if stage.type == "repo_context":
            output_path = self.artifacts.write_stage_output(
                task.id,
                stage.output or "context-pack.md",
                self._build_context_pack(task),
            )
            self.logger.event(
                "artifact.write",
                "Wrote context pack",
                stage_id=stage.id,
                task_id=task.id,
                artifact_path=output_path.relative_to(self.config.project.root),
            )
            return StageResult(
                stage_id=stage.id,
                status="pass",
                reason="Context pack written.",
                output_path=str(output_path.relative_to(self.config.project.root)),
            )
        if stage.type == "semantic_context":
            index = build_semantic_index(self.config.project.root, self.config.safety)
            index_path = self.artifacts.write_stage_output(
                task.id,
                "semantic-index.md",
                format_semantic_index(index),
            )
            query = " ".join([task.title, task.description, *task.acceptance_criteria])
            results = _task_semantic_results(index, query, task.id)
            context_path = self.artifacts.write_stage_output(
                task.id,
                stage.output or "semantic-context.md",
                format_search_results(results, query),
            )
            self.logger.event(
                "artifact.write",
                "Wrote semantic context",
                stage_id=stage.id,
                task_id=task.id,
                artifact_path=context_path.relative_to(self.config.project.root),
            )
            return StageResult(
                stage_id=stage.id,
                status="pass",
                reason="Semantic context written.",
                output_path=str(context_path.relative_to(self.config.project.root)),
                context_update=f"Semantic index: {index_path.relative_to(self.config.project.root).as_posix()}",
            )
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

    def _write_project_context_chart(self) -> Path:
        chart = build_project_context_chart(self.config.project.root, self.config.safety)
        self.artifacts.initialize_run()
        self.artifacts.project_context_chart_path.write_text(chart, encoding="utf-8")
        self.logger.event(
            "artifact.write",
            "Wrote project context chart",
            artifact_path=self.artifacts.project_context_chart_path.relative_to(self.config.project.root),
        )
        return self.artifacts.project_context_chart_path

    def _run_code_writer_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str],
        retry_notes: list[str],
        retry_count: int = 0,
    ) -> StageResult:
        if stage.agent is None:
            raise PipelineError(f"Pipeline error: code_writer stage '{stage.id}' must reference an agent.")
        enriched_outputs = dict(previous_outputs)
        context_pack_path = self._latest_task_artifact(task.id, "context-pack.md")
        if context_pack_path is not None:
            enriched_outputs["context-pack.md"] = context_pack_path.read_text(encoding="utf-8", errors="replace")
        chart_path = self.artifacts.project_context_chart_path
        if chart_path.exists():
            enriched_outputs["project-context-chart.md"] = chart_path.read_text(encoding="utf-8", errors="replace")
        context = self.context.read_context(task, retry_notes)
        agent_stage = self._writer_agent_stage(stage, retry_count)
        result = self.agent_executor.run_stage(
            agent_stage,
            task,
            enriched_outputs,
            retry_notes,
            project_context=context.project_context,
            task_context=context.task_context,
            retry_context=context.retry_context,
        )
        raw_output = self._read_output(result.output_path)
        stdout = extract_agent_stdout(raw_output)
        lookup_requests = parse_lookup_requests(stdout)
        if lookup_requests and "diff --git " not in stdout:
            lookup_context = self.repo_tools.execute_requests(
                task.id,
                lookup_requests,
                filename="implementation-files-inspected.md",
            )
            self.logger.event(
                "agent.rerun",
                "Re-running code writer with repo lookup context",
                stage_id=stage.id,
                task_id=task.id,
                lookup_count=len(lookup_requests),
            )
            rerun_outputs = dict(enriched_outputs)
            rerun_outputs["repo_lookup_results"] = lookup_context
            rerun_notes = [
                *retry_notes,
                "Repository lookup results have been provided. Return the unified diff now; do not request more lookups.",
            ]
            result = self.agent_executor.run_stage(
                agent_stage,
                task,
                rerun_outputs,
                rerun_notes,
                project_context=context.project_context,
                task_context=context.task_context,
                retry_context="\n".join(f"- {note}" for note in rerun_notes),
            )
            raw_output = self._read_output(result.output_path)
            stdout = extract_agent_stdout(raw_output)
        try:
            patch = extract_unified_diff(stdout)
        except PipelineError as exc:
            self.artifacts.write_stage_output(
                task.id,
                "implementation-summary.md",
                f"# Implementation Summary\n\nStatus: fail\nReason: {exc}\n",
            )
            return StageResult(stage.id, "fail", str(exc), output_path=result.output_path)
        patch_filename = _writer_patch_filename(stage, retry_count)
        summary_filename = _writer_summary_filename(stage, retry_count)
        proposed_path = self.artifacts.write_stage_output(task.id, patch_filename, patch)
        summary_path = self.artifacts.write_stage_output(
            task.id,
            summary_filename,
            format_implementation_summary(
                stage.id,
                proposed_path.relative_to(self.config.project.root).as_posix(),
                retry_count=retry_count,
                retry_notes=retry_notes,
            ),
        )
        self.logger.event(
            "artifact.write",
            "Wrote proposed patch",
            stage_id=stage.id,
            task_id=task.id,
            artifact_path=proposed_path.relative_to(self.config.project.root),
        )
        return StageResult(
            stage.id,
            "pass",
            "Proposed patch written.",
            output_path=str(proposed_path.relative_to(self.config.project.root)),
            context_update=f"Implementation summary: {summary_path.relative_to(self.config.project.root).as_posix()}",
        )

    def _run_file_writer_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str],
        retry_notes: list[str],
        retry_count: int = 0,
    ) -> StageResult:
        if stage.agent is None:
            raise PipelineError(f"Pipeline error: file_writer stage '{stage.id}' must reference an agent.")
        enriched_outputs = _file_writer_previous_outputs(previous_outputs, retry_count)
        context_pack_path = self._latest_task_artifact(task.id, "context-pack.md")
        if context_pack_path is not None:
            enriched_outputs["context-pack.md"] = context_pack_path.read_text(encoding="utf-8", errors="replace")
        chart_path = self.artifacts.project_context_chart_path
        if chart_path.exists():
            enriched_outputs["project-context-chart.md"] = chart_path.read_text(encoding="utf-8", errors="replace")
        context = self.context.read_context(task, retry_notes)
        agent_stage = self._writer_agent_stage(stage, retry_count)
        result = self.agent_executor.run_stage(
            agent_stage,
            task,
            enriched_outputs,
            retry_notes,
            project_context=context.project_context,
            task_context=context.task_context,
            retry_context=context.retry_context,
        )
        raw_output = self._read_output(result.output_path)
        stdout = extract_agent_stdout(raw_output)
        lookup_requests = parse_lookup_requests(stdout)
        if lookup_requests and "```file:" not in stdout.lower() and "```path:" not in stdout.lower():
            lookup_context = self.repo_tools.execute_requests(
                task.id,
                lookup_requests,
                filename="implementation-files-inspected.md",
            )
            self.logger.event(
                "agent.rerun",
                "Re-running file writer with repo lookup context",
                stage_id=stage.id,
                task_id=task.id,
                lookup_count=len(lookup_requests),
            )
            rerun_outputs = dict(enriched_outputs)
            rerun_outputs["repo_lookup_results"] = lookup_context
            rerun_notes = [
                *retry_notes,
                "Repository lookup results have been provided. Return complete file blocks now; do not request more lookups.",
            ]
            result = self.agent_executor.run_stage(
                agent_stage,
                task,
                rerun_outputs,
                rerun_notes,
                project_context=context.project_context,
                task_context=context.task_context,
                retry_context="\n".join(f"- {note}" for note in rerun_notes),
            )
            raw_output = self._read_output(result.output_path)
            stdout = extract_agent_stdout(raw_output)
        invalid_rerun_done = False
        candidate_index_path: Path | None = None
        while True:
            try:
                updates = parse_file_updates(stdout)
                candidate_index_path = self._write_file_writer_candidates(
                    task.id,
                    stage,
                    updates,
                    retry_count,
                )
                patch = generate_patch_from_file_updates(
                    updates,
                    self.config.project.root,
                    self.config.safety,
                    allowed_paths=stage.allowed_paths,
                    forbidden_paths=stage.forbidden_paths or DEFAULT_FORBIDDEN_PATHS,
                )
                patch_reason = "Deterministic patch written from file blocks."
                log_message = "Wrote deterministic patch from file blocks"
                break
            except PipelineError as exc:
                reason = _file_writer_error_reason(stage, str(exc))
                if (
                    "no file blocks found" in str(exc)
                    and "diff --git " not in stdout
                    and not invalid_rerun_done
                ):
                    invalid_rerun_done = True
                    self.logger.event(
                        "agent.rerun",
                        "Re-running file writer after invalid output",
                        stage_id=stage.id,
                        task_id=task.id,
                    )
                    rerun_outputs = dict(enriched_outputs)
                    rerun_outputs["invalid_file_writer_output_summary"] = _invalid_file_writer_output_summary(
                        stdout,
                        reason,
                    )
                    strict_notes = [
                        *retry_notes,
                        "Previous file_writer output was invalid. Return complete file blocks now. Do not output lookup_requests, prose, or 'lookup failed'.",
                        "Use complete fenced file blocks with both the opening ```file:path and closing ``` fence.",
                    ]
                    result = self.agent_executor.run_stage(
                        agent_stage,
                        task,
                        rerun_outputs,
                        strict_notes,
                        project_context=context.project_context,
                        task_context=context.task_context,
                        retry_context="\n".join(f"- {note}" for note in strict_notes),
                    )
                    raw_output = self._read_output(result.output_path)
                    stdout = extract_agent_stdout(raw_output)
                    continue
                try:
                    patch = normalize_patch_text(stdout)
                except PipelineError:
                    summary_filename = _writer_summary_filename(stage, retry_count)
                    if "generated patch has no changes" in reason:
                        next_stage = self._stage_after_patch_flow(stage.id)
                        reason = self._no_changes_reason(retry_count)
                        summary_path = self.artifacts.write_stage_output(
                            task.id,
                            summary_filename,
                            f"# Implementation Summary\n\nStatus: pass\nReason: {reason}\n",
                        )
                        return StageResult(
                            stage.id,
                            "pass",
                            reason,
                            output_path=result.output_path,
                            next_stage=next_stage,
                            context_update=(
                                f"Implementation summary: "
                                f"{summary_path.relative_to(self.config.project.root).as_posix()}"
                            ),
                        )
                    self.artifacts.write_stage_output(
                        task.id,
                        summary_filename,
                        f"# Implementation Summary\n\nStatus: fail\nReason: {reason}\n",
                    )
                    return StageResult(stage.id, "fail", reason, output_path=result.output_path)
                patch_reason = "Fallback patch written from unified diff output."
                log_message = "Wrote fallback patch from unified diff output"
                break
        patch_filename = _writer_patch_filename(stage, retry_count)
        summary_filename = _writer_summary_filename(stage, retry_count)
        proposed_path = self.artifacts.write_stage_output(task.id, patch_filename, patch)
        summary_path = self.artifacts.write_stage_output(
            task.id,
            summary_filename,
            format_implementation_summary(
                stage.id,
                proposed_path.relative_to(self.config.project.root).as_posix(),
                retry_count=retry_count,
                retry_notes=retry_notes,
                candidate_index_path=(
                    candidate_index_path.relative_to(self.config.project.root).as_posix()
                    if candidate_index_path
                    else None
                ),
            ),
        )
        self.logger.event(
            "artifact.write",
            log_message,
            stage_id=stage.id,
            task_id=task.id,
            artifact_path=proposed_path.relative_to(self.config.project.root),
        )
        return StageResult(
            stage.id,
            "pass",
            patch_reason,
            output_path=str(proposed_path.relative_to(self.config.project.root)),
            context_update=f"Implementation summary: {summary_path.relative_to(self.config.project.root).as_posix()}",
        )

    def _write_file_writer_candidates(
        self,
        task_id: str,
        stage: StageConfig,
        updates: tuple[FileUpdate, ...],
        retry_count: int,
    ) -> Path:
        if not updates:
            raise PipelineError("File writer error: no candidate file blocks found.")
        base = f"candidate-files/{stage.id}"
        if retry_count:
            base += f"-retry-{retry_count}"
        lines = [
            "# Candidate Files",
            "",
            f"Stage: `{stage.id}`",
            f"Retry: {retry_count}",
            "",
            "These are raw file blocks extracted before patch validation or apply.",
            "",
            "## Files",
            "",
        ]
        seen: set[str] = set()
        for index, update in enumerate(updates, start=1):
            filename = f"{index:03d}-{_candidate_artifact_name(update.path)}"
            while filename in seen:
                filename = f"{index:03d}-{len(seen):03d}-{_candidate_artifact_name(update.path)}"
            seen.add(filename)
            artifact_name = f"{base}/{filename}"
            artifact_path = self.artifacts.write_stage_output(task_id, artifact_name, update.content)
            relative = artifact_path.relative_to(self.config.project.root).as_posix()
            lines.extend(
                [
                    f"- Source path: `{update.path}`",
                    f"  Artifact: `{relative}`",
                ]
            )
        lines.append("")
        return self.artifacts.write_stage_output(task_id, f"{base}/index.md", "\n".join(lines))

    def _writer_agent_stage(self, stage: StageConfig, retry_count: int) -> StageConfig:
        suffix = f"-{retry_count}" if retry_count else ""
        return replace(
            self._stage_for_retry_agent(stage, retry_count),
            output=f"{stage.id}-agent-output{suffix}.md",
        )

    def _stage_after_patch_flow(self, current_stage_id: str) -> str | None:
        stages = list(self.config.pipeline.stages)
        stage_indexes = {stage.id: index for index, stage in enumerate(stages)}
        start = stage_indexes.get(current_stage_id)
        if start is None:
            return None
        patch_stage_types = {"patch_normalizer", "patch_validator", "patch_apply"}
        for stage in stages[start + 1:]:
            if stage.type in patch_stage_types:
                continue
            return stage.id
        return None

    def _no_changes_reason(self, retry_count: int) -> str:
        if retry_count:
            return (
                "File writer produced no changes relative to the current workspace. "
                "The previous patch may already be applied; skipping patch stages and "
                "continuing with verification."
            )
        return (
            "File writer produced no changes relative to the current workspace. "
            "The task may already be applied locally; skipping patch stages and "
            "continuing with verification."
        )

    def _run_patch_normalizer_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str],
        retry_notes: list[str],
        retry_count: int = 0,
    ) -> StageResult:
        source = _latest_patch_like_output(previous_outputs)
        if stage.agent is not None:
            result = self.agent_executor.run_stage(
                stage,
                task,
                {"patch_input": source, **previous_outputs},
                retry_notes,
                project_context=self.context.read_context(task, retry_notes).project_context,
                task_context=self.context.read_context(task, retry_notes).task_context,
                retry_context=self.context.read_context(task, retry_notes).retry_context,
            )
            source = extract_agent_stdout(self._read_output(result.output_path))
        try:
            patch = normalize_patch_text(source)
        except PipelineError as exc:
            return StageResult(stage.id, "fail", str(exc))
        output_path = self.artifacts.write_stage_output(
            task.id,
            _attempt_filename(stage.output or "normalized.patch", retry_count),
            patch,
        )
        self.logger.event(
            "artifact.write",
            "Wrote normalized patch",
            stage_id=stage.id,
            task_id=task.id,
            artifact_path=output_path.relative_to(self.config.project.root),
        )
        return StageResult(
            stage.id,
            "pass",
            "Normalized patch written.",
            output_path=str(output_path.relative_to(self.config.project.root)),
        )

    def _run_patch_validator_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str],
        retry_count: int = 0,
    ) -> StageResult:
        output_filename = _attempt_filename(stage.output or "patch-validation.md", retry_count)
        source = _latest_patch_like_output(previous_outputs)
        try:
            patch = normalize_patch_text(source)
            result = validate_patch(
                patch,
                self.config.project.root,
                self.config.safety,
                max_files=stage.max_files or DEFAULT_MAX_FILES,
                max_changed_lines=stage.max_lines or DEFAULT_MAX_CHANGED_LINES,
                max_delete_ratio=stage.max_delete_ratio,
                allowed_paths=stage.allowed_paths,
                forbidden_paths=stage.forbidden_paths or DEFAULT_FORBIDDEN_PATHS,
            )
        except PipelineError as exc:
            output_path = self.artifacts.write_stage_output(
                task.id,
                output_filename,
                f"# Patch Validation\n\nStatus: fail\nReason: {exc}\n",
            )
            return StageResult(
                stage.id,
                "fail",
                str(exc),
                output_path=str(output_path.relative_to(self.config.project.root)),
            )
        output_path = self.artifacts.write_stage_output(
            task.id,
            output_filename,
            format_validation_result(result),
        )
        return StageResult(
            stage.id,
            "pass",
            "Patch validation passed.",
            output_path=str(output_path.relative_to(self.config.project.root)),
        )

    def _run_patch_apply_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str],
        retry_count: int = 0,
    ) -> StageResult:
        output_filename = _attempt_filename(stage.output or "patch-apply-output.txt", retry_count)
        source = _latest_patch_like_output(previous_outputs)
        try:
            patch = normalize_patch_text(source)
            validate_patch(
                patch,
                self.config.project.root,
                self.config.safety,
                max_files=stage.max_files or DEFAULT_MAX_FILES,
                max_changed_lines=stage.max_lines or DEFAULT_MAX_CHANGED_LINES,
                max_delete_ratio=stage.max_delete_ratio,
                allowed_paths=stage.allowed_paths,
                forbidden_paths=stage.forbidden_paths or DEFAULT_FORBIDDEN_PATHS,
            )
        except PipelineError as exc:
            output_path = self.artifacts.write_stage_output(
                task.id,
                output_filename,
                f"# Patch Apply\n\nStatus: fail\nReason: {exc}\n",
            )
            return StageResult(
                stage.id,
                "fail",
                str(exc),
                output_path=str(output_path.relative_to(self.config.project.root)),
            )

        applied_path = self.artifacts.write_stage_output(
            task.id,
            _attempt_filename("applied.patch", retry_count),
            patch,
        )
        write_git_artifacts(self.artifacts, task.id, "before-patch-apply")
        mode = stage.mode or "dry_run"
        apply_result = apply_patch_with_git(applied_path, self.config.project.root, mode=mode)
        write_git_artifacts(self.artifacts, task.id, "after-patch-apply")
        output_path = self.artifacts.write_stage_output(
            task.id,
            output_filename,
            format_patch_apply_result(
                apply_result,
                applied_path.relative_to(self.config.project.root).as_posix(),
            ),
        )
        if apply_result.status != "pass":
            return StageResult(
                stage.id,
                "fail",
                f"Patch apply failed with code {apply_result.exit_code}.",
                output_path=str(output_path.relative_to(self.config.project.root)),
                context_update=apply_result.stderr.strip() or apply_result.stdout.strip(),
            )
        reason = "Patch dry run passed." if mode == "dry_run" else "Patch applied."
        return StageResult(
            stage.id,
            "pass",
            reason,
            output_path=str(output_path.relative_to(self.config.project.root)),
        )

    def _latest_task_artifact(self, task_id: str, filename: str) -> Path | None:
        path = self.artifacts.create_task_dir(task_id).directory / filename
        return path if path.exists() else None

    def _stage_for_retry_agent(self, stage: StageConfig, retry_count: int) -> StageConfig:
        if not stage.agent_pool:
            return stage
        index = min(retry_count, len(stage.agent_pool) - 1)
        return replace(stage, agent=stage.agent_pool[index])

    def _maybe_satisfy_resource_request(
        self,
        stage: StageConfig,
        task: Task,
        result: StageResult,
    ) -> StageResult | None:
        output_text = self._read_output(result.output_path)
        requests = parse_resource_requests(extract_agent_stdout(output_text))
        if not requests:
            return None
        paths = satisfy_resource_requests(self.artifacts, task.id, requests)
        report_path = self.artifacts.write_stage_output(
            task.id,
            "resource-requests.md",
            format_resource_report(requests, paths, self.config.project.root),
        )
        return StageResult(
            stage.id,
            "pass",
            "Blocked resource requests were satisfied in the active run directory.",
            output_path=str(report_path.relative_to(self.config.project.root)),
            context_update=(
                "Generated run-local resources: "
                + ", ".join(path.relative_to(self.config.project.root).as_posix() for path in paths)
            ),
        )

    def _write_failure_diagnostics(
        self,
        stage: StageConfig,
        task: Task,
        result: StageResult,
        retry_count: int,
    ) -> str:
        output = self._read_output(result.output_path)
        if not output and not result.reason:
            return ""
        exit_code = _extract_exit_code(output) or _extract_exit_code(result.reason)
        modified_files = self._modified_files()
        classification = classify_failure(
            "\n".join([result.reason, output]),
            exit_code=exit_code,
            modified_files=modified_files,
        )
        filename = f"diagnostics/{stage.id}-failure"
        if retry_count:
            filename += f"-retry-{retry_count}"
        filename += ".md"
        diagnostic_path = self.artifacts.write_stage_output(
            task.id,
            filename,
            format_failure_classification(
                classification,
                exit_code=exit_code,
                modified_files=modified_files,
            ),
        )
        if classification.category == "missing dependency":
            dependency_path = self.artifacts.write_stage_output(
                task.id,
                "diagnostics/dependency-diagnostic.md",
                format_dependency_diagnostic(
                    diagnose_python_dependencies(self.config.project.root, output)
                ),
            )
            return (
                f"Failure classification: {classification.category}; "
                f"diagnostic: {diagnostic_path.relative_to(self.config.project.root).as_posix()}; "
                f"dependency diagnostic: {dependency_path.relative_to(self.config.project.root).as_posix()}."
            )
        return (
            f"Failure classification: {classification.category}; "
            f"root cause: {classification.probable_root_cause}; "
            f"diagnostic: {diagnostic_path.relative_to(self.config.project.root).as_posix()}."
        )

    def _run_debugger_if_configured(
        self,
        task: Task,
        result: StageResult,
        retry_notes: list[str],
    ) -> str:
        debugger_id = next(
            (
                agent_id
                for agent_id, agent in self.config.agents.items()
                if agent.role == "debugger" or agent_id == "debugger"
            ),
            None,
        )
        if debugger_id is None:
            return ""
        stage = StageConfig(
            id="debugger",
            type="agent",
            agent=debugger_id,
            output="debugger.md",
        )
        output = self._read_output(result.output_path)
        context = self.context.read_context(task, retry_notes)
        debug_result = self.agent_executor.run_stage(
            stage,
            task,
            {"failed_stage": result.reason, "failure_output": output},
            retry_notes,
            project_context=context.project_context,
            task_context=context.task_context,
            retry_context=context.retry_context,
        )
        return f"Debugger output: {debug_result.output_path or 'none'}."

    def _modified_files(self) -> tuple[str, ...]:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.config.project.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            return ()
        files: list[str] = []
        for line in completed.stdout.splitlines():
            if len(line) > 3:
                files.append(line[3:].strip())
        return tuple(files)

    def _telemetry_entry(
        self,
        stage: StageConfig,
        result: StageResult,
        retry_count: int,
    ) -> TelemetryEntry:
        effective_stage = self._stage_for_retry_agent(stage, retry_count)
        agent = self.config.agents.get(effective_stage.agent) if effective_stage.agent else None
        return telemetry_from_stage_output(
            stage_id=result.stage_id,
            stage_type=stage.type,
            status=result.status,
            output=self._read_output(result.output_path),
            retry_count=retry_count,
            agent_id=agent.id if agent else None,
            model=agent.model if agent else None,
        )

    def _write_telemetry(self, task_id: str, entries: list[TelemetryEntry]) -> None:
        summary = format_telemetry_summary(tuple(entries))
        self.artifacts.write_stage_output(task_id, "telemetry-summary.md", summary)
        self.artifacts.run_dir.joinpath("telemetry-summary.md").write_text(summary, encoding="utf-8")

    def _maybe_rerun_agent_with_repo_lookup(
        self,
        stage: StageConfig,
        task: Task,
        result: StageResult,
        previous_outputs: dict[str, str],
        retry_notes: list[str],
        project_context: str,
        task_context: str,
        retry_context: str | None,
    ) -> StageResult:
        if result.status != "pass" or result.output_path is None:
            return result
        output_text = self._read_output(result.output_path)
        requests = parse_lookup_requests(extract_agent_stdout(output_text))
        if not requests:
            return result
        lookup_context = self.repo_tools.execute_requests(
            task.id,
            requests,
            filename="files-inspected.md",
        )
        self.logger.event(
            "agent.rerun",
            "Re-running agent with repo lookup context",
            stage_id=stage.id,
            task_id=task.id,
            lookup_count=len(requests),
        )
        rerun_outputs = dict(previous_outputs)
        rerun_outputs["repo_lookup_results"] = lookup_context
        rerun_retry_notes = [
            *retry_notes,
            "Repository lookup results have been provided. Write the final plan now; do not request more lookups.",
        ]
        rerun_result = self.agent_executor.run_stage(
            stage,
            task,
            rerun_outputs,
            rerun_retry_notes,
            project_context=project_context,
            task_context=task_context,
            retry_context="\n".join(f"- {note}" for note in rerun_retry_notes),
        )
        return StageResult(
            stage_id=rerun_result.stage_id,
            status=rerun_result.status,
            reason=(
                "Agent completed after repo lookup."
                if rerun_result.status == "pass"
                else rerun_result.reason
            ),
            output_path=rerun_result.output_path,
            next_stage=rerun_result.next_stage,
            context_update=rerun_result.context_update,
        )

    def _build_context_pack(self, task: Task) -> str:
        terms = _task_search_terms(task)
        lookup_paths = self.config.safety.scoped_paths or (".",)
        files = self._list_context_files(lookup_paths, task.id)
        grep_sections: list[str] = []
        for term in terms[:5]:
            scoped_results = []
            for path in lookup_paths:
                grep_output = self.repo_tools.grep(re.escape(term), path, max_matches=20).rstrip()
                grep_output = _filter_future_task_test_lines(grep_output, task.id)
                scoped_results.append(
                    f"#### Path: {path}\n\n"
                    "```text\n"
                    f"{grep_output}\n"
                    "```"
                )
            grep_sections.extend(
                [
                    f"### Search: {term}",
                    "",
                    *scoped_results,
                    "",
                ]
            )
        return "\n".join(
            [
                "# Context Pack",
                "",
                f"Task: `{task.id}`",
                f"Title: {task.title}",
                "",
                "## Acceptance Criteria",
                "",
                "\n".join(f"- {item}" for item in task.acceptance_criteria) or "- None",
                "",
                "## Constraints",
                "",
                f"- Scoped paths: {', '.join(self.config.safety.scoped_paths) or '.'}",
                "- Repository lookups are read-only.",
                "- Excerpts are line-numbered where files are read directly.",
                "",
                "## Relevant Files",
                "",
                "```text",
                files,
                "```",
                "",
                "## Search Results",
                "",
                *grep_sections,
            ]
        )

    def _list_context_files(self, paths: tuple[str, ...], task_id: str) -> str:
        sections: list[str] = []
        for path in paths:
            files = self.repo_tools.list_files(path, pattern="*", max_files=80).rstrip()
            files = _filter_future_task_test_lines(files, task_id)
            sections.extend(
                [
                    f"## Path: {path}",
                    files,
                    "",
                ]
            )
        return "\n".join(sections).strip() or "No files found."

    def _read_output(self, output_path: str | None) -> str:
        if output_path is None:
            return ""
        path = self.config.project.root / Path(output_path)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _format_retry_note(
        self,
        retry_count: int,
        stage: StageConfig,
        result: StageResult,
        target_stage: str,
    ) -> str:
        note = (
            f"Retry {retry_count}: stage '{stage.id}' returned "
            f"{result.status} ({result.reason}); redirecting to '{target_stage}'."
        )
        excerpt = self._failure_excerpt(result.output_path)
        if not excerpt:
            return note
        return f"{note}\n\nRelevant failure output:\n```text\n{excerpt}\n```"

    def _failure_excerpt(self, output_path: str | None, max_chars: int = 3500) -> str:
        content = self._read_output(output_path)
        if not content.strip():
            return ""
        cleaned_content = re.sub(r"\n{4,}", "\n\n\n", content.strip())
        if len(cleaned_content) <= max_chars:
            return cleaned_content
        patterns = (
            "error",
            "fail",
            "traceback",
            "assertionerror",
            "exception",
            "exit code",
            "stderr",
            "stdout",
            "timed out",
        )
        lines = content.splitlines()
        selected = [
            line
            for line in lines
            if any(pattern in line.lower() for pattern in patterns)
        ]
        excerpt = "\n".join(selected).strip()
        if len(excerpt) < 400:
            excerpt = content.strip()
        excerpt = re.sub(r"\n{4,}", "\n\n\n", excerpt)
        if len(excerpt) <= max_chars:
            return excerpt
        return excerpt[:max_chars].rstrip() + "\n... <truncated>"

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


def format_implementation_summary(
    stage_id: str,
    patch_path: str,
    retry_count: int = 0,
    retry_notes: list[str] | None = None,
    candidate_index_path: str | None = None,
) -> str:
    notes = retry_notes or []
    lines = [
        "# Implementation Summary",
        "",
        f"Stage: `{stage_id}`",
        "Status: pass",
        f"Repair attempt: {retry_count}",
        f"Patch: `{patch_path}`",
        f"Candidate files: `{candidate_index_path}`" if candidate_index_path else "Candidate files: <none>",
        "",
        "## Retry Feedback",
        "",
    ]
    lines.extend(f"- {note}" for note in notes[-5:]) if notes else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _latest_patch_like_output(previous_outputs: dict[str, str]) -> str:
    for name in ("normalized.patch", "applied.patch", "proposed.patch", "patch_input"):
        if name in previous_outputs and previous_outputs[name].strip():
            return previous_outputs[name]
    for stage_id, content in reversed(list(previous_outputs.items())):
        if stage_id.endswith(".patch") or "diff --git " in content or "\n--- " in content:
            return content
    raise PipelineError("Patch error: no previous patch output found.")


def _writer_patch_filename(stage: StageConfig, retry_count: int) -> str:
    if retry_count <= 0:
        return stage.output or "proposed.patch"
    if stage.type == "code_writer" or stage.id == "implement":
        return f"repair-{retry_count}.patch"
    return _attempt_filename(stage.output or f"{stage.id}.patch", retry_count)


def _writer_summary_filename(stage: StageConfig, retry_count: int) -> str:
    if stage.type == "code_writer" or stage.id == "implement":
        return "implementation-summary.md" if retry_count <= 0 else f"repair-summary-{retry_count}.md"
    base = f"{stage.id}-summary.md"
    return base if retry_count <= 0 else _attempt_filename(base, retry_count)


def _attempt_filename(filename: str, retry_count: int) -> str:
    if retry_count <= 0:
        return filename
    path = Path(filename)
    suffix = "".join(path.suffixes)
    if suffix:
        stem = path.name[: -len(suffix)]
        name = f"{stem}-{retry_count}{suffix}"
    else:
        name = f"{path.name}-{retry_count}"
    return path.with_name(name).as_posix()


def _stage_with_attempt_output(stage: StageConfig, retry_count: int) -> StageConfig:
    if retry_count <= 0:
        return stage
    output = _attempt_filename(stage.output or f"{stage.id}-output.txt", retry_count)
    return replace(stage, output=output)


def _extract_exit_code(text: str) -> int | None:
    match = re.search(r"Exit code:\s*(-?\d+)|code\s+(-?\d+)", text)
    if not match:
        return None
    value = match.group(1) or match.group(2)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _task_semantic_results(index, query: str, task_id: str):
    current_test_path = _current_task_test_path(task_id)
    current = tuple(item for item in index if item.path == current_test_path)
    current_paths = {item.path for item in current}
    searched = search_index(index, query, limit=8)
    filtered = tuple(
        item
        for item in searched
        if item.path not in current_paths and not _future_task_test_path(item.path, current_test_path)
    )
    return (*current, *filtered)[:8]


def _future_task_test_path(path: str, current_test_path: str) -> bool:
    return bool(re.fullmatch(r"tests/test_task\d+\.py", path)) and path != current_test_path


def _current_task_test_path(task_id: str) -> str:
    return f"tests/test_{task_id.lower().replace('-', '')}.py"


def _filter_future_task_test_lines(text: str, task_id: str) -> str:
    current_test_path = _current_task_test_path(task_id)
    kept: list[str] = []
    for line in text.splitlines():
        normalized = line.replace("\\", "/")
        matches = re.findall(r"tests/test_task\d+\.py", normalized)
        if matches and all(path != current_test_path for path in matches):
            continue
        kept.append(line)
    return "\n".join(kept)


def _invalid_file_writer_output_summary(output: str, reason: str, max_chars: int = 1200) -> str:
    lines = [
        f"Reason: {reason}",
        f"Output length: {len(output)} characters",
    ]
    lowered = output.lower()
    if "```file:" in lowered or "```path:" in lowered:
        lines.append("The output started a file block, but NightShift could not parse a complete closed block.")
    else:
        lines.append("The output did not contain a parseable file block.")
    excerpt = output.strip()
    if excerpt:
        if len(excerpt) > max_chars:
            excerpt = excerpt[:max_chars].rstrip() + "\n... <truncated>"
        lines.extend(["", "Excerpt:", "```text", excerpt, "```"])
    return "\n".join(lines)


def _file_writer_error_reason(stage: StageConfig, reason: str) -> str:
    guidance = _file_writer_stage_guidance(stage)
    if not guidance or "not allowed for this stage" not in reason:
        return reason
    return f"{reason} {guidance}"


def _file_writer_stage_guidance(stage: StageConfig) -> str:
    allowed = tuple(path.replace("\\", "/").rstrip("/") for path in stage.allowed_paths)
    if allowed == ("story/chapters",):
        return (
            "This is the drafting stage: write only scene prose under `story/chapters/`. "
            "Do not update plot state, characters, timeline, unresolved threads, or other story state files."
        )
    state_paths = {
        "story/plot-state.md",
        "story/characters.md",
        "story/timeline.md",
        "story/unresolved-threads.md",
    }
    if set(allowed).issubset(state_paths) and allowed:
        return (
            "This is the state update stage: update only durable story state files. "
            "Do not rewrite scene prose or chapter files."
        )
    if allowed:
        return "Return file blocks only for the allowed paths configured on this stage."
    return ""


def _candidate_artifact_name(path_text: str) -> str:
    name = path_text.replace("\\", "/").strip().strip("/")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    name = name.strip("._-")
    return name or "candidate.txt"


def _file_writer_previous_outputs(
    previous_outputs: dict[str, str],
    retry_count: int,
    max_chars: int = 1200,
) -> dict[str, str]:
    if retry_count <= 0:
        return dict(previous_outputs)
    compacted: dict[str, str] = {}
    for name, output in previous_outputs.items():
        compacted[name] = _compact_previous_output(output, max_chars=max_chars)
    return compacted


def _compact_previous_output(output: str, max_chars: int = 1200) -> str:
    if len(output) <= max_chars:
        return output
    head_chars = max_chars // 2
    tail_chars = max_chars - head_chars
    return (
        output[:head_chars].rstrip()
        + "\n\n... <previous output truncated for retry prompt> ...\n\n"
        + output[-tail_chars:].lstrip()
    )


def _repeated_protected_path_violation(entries: tuple[RetryMemoryEntry, ...]) -> bool:
    recent = entries[-2:]
    if len(recent) < 2:
        return False
    return all(_is_protected_path_violation(entry.cause) for entry in recent)


def _is_protected_path_violation(text: str) -> bool:
    lowered = text.lower()
    return "not allowed for this stage" in lowered and "tests/" in lowered.replace("\\", "/")


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
                f"- Temperature: {agent.temperature if agent.temperature is not None else ''}",
                f"- Base URL: {agent.base_url or ''}",
                f"- Command: {agent.command or ''}",
                f"- System prompt: {agent.system_prompt}",
                "",
            ]
        )
    return "\n".join(lines)


def _task_search_terms(task: Task) -> list[str]:
    source = " ".join([task.id, task.title, *task.acceptance_criteria])
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", source)
    ignored = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "task",
        "add",
        "use",
        "can",
        "should",
        "must",
    }
    terms: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in ignored or lowered in terms:
            continue
        terms.append(lowered)
    return terms or [task.id]
