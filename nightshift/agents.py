"""Command-backed agent execution."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib import request
from urllib.error import URLError

from .artifacts import ArtifactStore
from .config import AgentConfig, StageConfig
from .errors import AgentError, SafetyError
from .runlog import NullRunLogger, RunLogger
from .safety import resolve_inside_root, resolve_project_root
from .stages import StageResult, StageStatus
from .tasks import Task


DEFAULT_AGENT_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class AgentInvocation:
    agent_id: str
    command: str
    prompt: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


class AgentExecutor:
    """Execute configured agents.

    Supports command-backed agents and a first-class Ollama backend. Both
    receive the same prompt bundle on stdin and persist comparable artifacts.
    """

    def __init__(
        self,
        project_root: str | Path,
        agents: dict[str, AgentConfig],
        artifacts: ArtifactStore,
        timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS,
        logger: RunLogger | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.agents = agents
        self.artifacts = artifacts
        self.timeout_seconds = timeout_seconds
        self.logger = logger or NullRunLogger()

    def run_stage(
        self,
        stage: StageConfig,
        task: Task,
        previous_outputs: dict[str, str] | None = None,
        retry_notes: list[str] | None = None,
        project_context: str | None = None,
        task_context: str | None = None,
        retry_context: str | None = None,
    ) -> StageResult:
        if stage.agent is None:
            raise AgentError(f"Agent error: stage '{stage.id}' does not reference an agent.")
        agent = self.agents.get(stage.agent)
        if agent is None:
            raise AgentError(f"Agent error: unknown agent '{stage.agent}' for stage '{stage.id}'.")
        if agent.backend not in {"command", "ollama", "openai_compatible"}:
            raise AgentError(
                f"Agent error: agent '{agent.id}' uses unsupported backend '{agent.backend}'."
            )
        if agent.backend == "command" and not agent.command:
            raise AgentError(f"Agent error: command backend agent '{agent.id}' has no command.")
        if agent.backend == "ollama" and not agent.model:
            raise AgentError(f"Agent error: ollama backend agent '{agent.id}' has no model.")
        if agent.backend == "openai_compatible" and not agent.model:
            raise AgentError(f"Agent error: openai_compatible backend agent '{agent.id}' has no model.")
        if agent.backend == "openai_compatible" and not agent.base_url:
            raise AgentError(f"Agent error: openai_compatible backend agent '{agent.id}' has no base_url.")

        system_prompt = self._read_system_prompt(agent)
        prompt = build_prompt_bundle(
            system_prompt=system_prompt,
            stage=stage,
            task=task,
            project_context=project_context if project_context is not None else self._read_project_context(),
            task_context=task_context or "",
            previous_outputs=previous_outputs or {},
            retry_notes=retry_notes or [],
            retry_context=retry_context,
        )
        self.logger.event(
            "agent.start",
            "Starting agent",
            stage_id=stage.id,
            agent_id=agent.id,
            backend=agent.backend,
            model=agent.model,
            temperature=agent.temperature,
        )
        invocation = self._invoke(agent, prompt)
        self.logger.event(
            "agent.finish",
            "Finished agent",
            stage_id=stage.id,
            agent_id=agent.id,
            backend=agent.backend,
            exit_code=invocation.exit_code,
            duration=f"{invocation.duration_seconds:.3f}s",
            timed_out=str(invocation.timed_out).lower(),
        )
        output_filename = stage.output or f"{stage.id}.md"
        output = format_agent_invocation(stage.id, invocation)
        output_path = self.artifacts.write_stage_output(task.id, output_filename, output)
        json_output_path = self.artifacts.write_stage_output(
            task.id,
            _agent_invocation_json_filename(output_filename),
            format_agent_invocation_json(stage.id, invocation),
        )
        self.logger.event(
            "artifact.write",
            "Wrote agent artifact",
            stage_id=stage.id,
            task_id=task.id,
            agent_id=agent.id,
            artifact_path=output_path.relative_to(self.project_root),
            json_artifact_path=json_output_path.relative_to(self.project_root),
        )

        if invocation.timed_out:
            status: StageStatus = "fail"
            reason = f"Agent timed out after {self.timeout_seconds}s."
            next_stage = None
            context_update = None
        elif invocation.exit_code != 0:
            status = "fail"
            reason = f"Agent exited with code {invocation.exit_code}."
            next_stage = None
            context_update = None
        elif stage.type in {"agent_review", "review"}:
            status, reason, next_stage, context_update = parse_review_output(invocation.stdout)
        else:
            status = "pass"
            reason = "Agent completed."
            next_stage = None
            context_update = None

        return StageResult(
            stage_id=stage.id,
            status=status,
            reason=reason,
            output_path=str(output_path.relative_to(self.project_root)),
            next_stage=next_stage,
            context_update=context_update,
        )

    def _read_system_prompt(self, agent: AgentConfig) -> str:
        try:
            path = resolve_inside_root(
                self.project_root, agent.system_prompt, f"agent '{agent.id}' system prompt"
            )
        except SafetyError as exc:
            raise AgentError(str(exc)) from exc
        if not path.exists():
            raise AgentError(f"Agent error: system prompt does not exist: {agent.system_prompt}")
        return path.read_text(encoding="utf-8")

    def _read_project_context(self) -> str:
        if not self.artifacts.project_context_path.exists():
            return ""
        return self.artifacts.project_context_path.read_text(encoding="utf-8")

    def _invoke(self, agent: AgentConfig, prompt: str) -> AgentInvocation:
        if agent.backend == "ollama":
            return self._invoke_ollama(agent, prompt)
        if agent.backend == "openai_compatible":
            return self._invoke_openai_compatible(agent, prompt)
        return self._invoke_command(agent, prompt)

    def _invoke_command(self, agent: AgentConfig, prompt: str) -> AgentInvocation:
        if not agent.command:
            raise AgentError(f"Agent error: command backend agent '{agent.id}' has no command.")
        started = time.monotonic()
        try:
            completed = subprocess.run(
                agent.command,
                cwd=self.project_root,
                shell=True,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=agent.command,
                prompt=prompt,
                exit_code=completed.returncode,
                stdout=_coerce_output(completed.stdout),
                stderr=_coerce_output(completed.stderr),
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=agent.command,
                prompt=prompt,
                exit_code=-1,
                stdout=_coerce_output(exc.stdout),
                stderr=_coerce_output(exc.stderr),
                duration_seconds=duration,
                timed_out=True,
            )

    def _invoke_ollama(self, agent: AgentConfig, prompt: str) -> AgentInvocation:
        if not agent.model:
            raise AgentError(f"Agent error: ollama backend agent '{agent.id}' has no model.")
        base_url = (agent.base_url or "http://localhost:11434").rstrip("/")
        url = base_url + "/api/generate"
        command = f"POST {url}"
        body: dict[str, object] = {
            "model": agent.model,
            "prompt": prompt,
            "stream": False,
        }
        options = _ollama_options(agent)
        if options:
            body["options"] = options
        headers = {"Content-Type": "application/json"}
        started = time.monotonic()
        self.logger.event(
            "ollama.start",
            "Starting Ollama HTTP model invocation",
            agent_id=agent.id,
            model=agent.model,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            payload = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=command,
                prompt=prompt,
                exit_code=0,
                stdout=_extract_ollama_response(raw),
                stderr="",
                duration_seconds=duration,
            )
        except TimeoutError:
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=command,
                prompt=prompt,
                exit_code=-1,
                stdout="",
                stderr="Request timed out.",
                duration_seconds=duration,
                timed_out=True,
            )
        except (OSError, URLError) as exc:
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=command,
                prompt=prompt,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                duration_seconds=duration,
            )

    def _invoke_openai_compatible(self, agent: AgentConfig, prompt: str) -> AgentInvocation:
        if not agent.model or not agent.base_url:
            raise AgentError(f"Agent error: openai_compatible backend agent '{agent.id}' is incomplete.")
        url = agent.base_url.rstrip("/") + "/chat/completions"
        command = f"POST {url}"
        body: dict[str, object] = {
            "model": agent.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if agent.temperature is not None:
            body["temperature"] = agent.temperature
        headers = {"Content-Type": "application/json"}
        api_key_env = agent.api_key_env or "OPENAI_API_KEY"
        api_key = os.environ.get(api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        started = time.monotonic()
        try:
            payload = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=command,
                prompt=prompt,
                exit_code=0,
                stdout=_extract_openai_content(raw),
                stderr="",
                duration_seconds=duration,
            )
        except TimeoutError:
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=command,
                prompt=prompt,
                exit_code=-1,
                stdout="",
                stderr="Request timed out.",
                duration_seconds=duration,
                timed_out=True,
            )
        except (OSError, URLError) as exc:
            duration = time.monotonic() - started
            return AgentInvocation(
                agent_id=agent.id,
                command=command,
                prompt=prompt,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                duration_seconds=duration,
            )


def build_prompt_bundle(
    system_prompt: str,
    stage: StageConfig,
    task: Task,
    project_context: str,
    previous_outputs: dict[str, str],
    retry_notes: list[str],
    task_context: str = "",
    retry_context: str | None = None,
) -> str:
    acceptance = "\n".join(f"- {item}" for item in task.acceptance_criteria)
    prior = "\n\n".join(f"## {stage_id}\n\n{content}" for stage_id, content in previous_outputs.items())
    retries = "\n".join(f"- {note}" for note in retry_notes)

    return "\n".join(
        [
            "# NightShift Agent Input",
            "",
            "## System Prompt",
            "",
            system_prompt.strip(),
            "",
            "## Stage",
            "",
            f"- id: {stage.id}",
            f"- type: {stage.type}",
            "",
            "## Task",
            "",
            task.raw_markdown.strip(),
            "",
            "## Acceptance Criteria",
            "",
            acceptance,
            "",
            "## Project Context",
            "",
            project_context.strip(),
            "",
            "## Task Context",
            "",
            task_context.strip(),
            "",
            "## Previous Stage Output",
            "",
            prior.strip(),
            "",
            "## Retry Notes",
            "",
            (retry_context if retry_context is not None else retries).strip(),
            "",
            "## Output Contract",
            "",
            output_contract_for(stage),
            "",
        ]
    )


def _ollama_options(agent: AgentConfig) -> dict[str, object]:
    options: dict[str, object] = {}
    if agent.temperature is not None:
        options["temperature"] = agent.temperature
    if agent.num_ctx is not None:
        options["num_ctx"] = agent.num_ctx
    if agent.num_predict is not None:
        options["num_predict"] = agent.num_predict
    if agent.seed is not None:
        options["seed"] = agent.seed
    if agent.stop:
        options["stop"] = list(agent.stop)
    return options


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return strip_ansi_escape_sequences(value)


def strip_ansi_escape_sequences(value: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)


def _extract_openai_content(raw: str) -> str:
    try:
        data = json.loads(raw)
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content
    except (json.JSONDecodeError, AttributeError):
        pass
    return raw


def _extract_ollama_response(raw: str) -> str:
    try:
        data = json.loads(raw)
        response = data.get("response")
        if isinstance(response, str):
            return response
    except (json.JSONDecodeError, AttributeError):
        pass
    return raw


def output_contract_for(stage: StageConfig) -> str:
    if stage.type == "code_writer":
        return "\n".join(
            [
                "Return a unified diff only, suitable for saving as proposed.patch or repair-N.patch.",
                "Do not include prose outside the patch.",
                "Use diff --git headers and hunk headers.",
                "For existing files, do not use new file mode or /dev/null headers.",
                "On repair attempts, return a complete corrected replacement diff.",
            ]
        )
    if stage.type == "file_writer":
        contract = _file_writer_block_contract(stage)
        allowed = _format_allowed_file_writer_paths(stage.allowed_paths)
        return "\n".join(
            [
                "Return complete file contents only.",
                contract,
                allowed,
                "Do not include prose outside file blocks or delimiter blocks.",
                "Include only files required for this stage and task.",
                "NightShift will generate the unified diff deterministically.",
                "On repair attempts, use the retry notes and failed stage output to diagnose the root cause before changing files.",
                "Do not repeat an unchanged solution unless the failure output shows the implementation is already correct.",
            ]
        )
    if stage.type == "patch_normalizer":
        return "\n".join(
            [
                "Convert the supplied patch-like content to one valid unified diff.",
                "Return only the normalized patch.",
                "If the edit is missing or ambiguous, say that no valid unified diff can be produced.",
            ]
        )
    if stage.type in {"agent_review", "review"}:
        return "\n".join(
            [
                "Output exactly:",
                "status: pass | fail | retry | escalate",
                "reason: <short explanation>",
                "next_stage: <optional stage id>",
                "context_update: <compact useful note>",
            ]
        )
    if stage.type == "agent" and ("plan" in stage.id.lower() or stage.agent == "planner"):
        return "\n".join(
            [
                "Write the requested stage output in concise markdown.",
                "",
                "If you need repository context before finalizing the plan, include:",
                "lookup_requests:",
                "- tool: list_files | read_file | grep",
                "  path: <relative path>",
                "  pattern: <glob for list_files or regex for grep>",
                "",
                "Use at most 5 lookup requests.",
                "Do not repeat the same lookup request.",
                "Prefer read_file for likely-relevant files over many grep variations.",
                "Do not search .nightshift, .git, virtualenvs, caches, or artifact directories.",
                "",
                "NightShift will run these read-only lookup tools, save files-inspected.md, and re-run this planner stage with the retrieved context.",
            ]
        )
    return "Write the requested stage output in concise markdown."


def _file_writer_block_contract(stage: StageConfig) -> str:
    normalized = tuple(path.replace("\\", "/").rstrip("/") for path in stage.allowed_paths)
    if normalized == ("story/chapters",):
        return "\n".join(
            [
                "Use exactly this delimiter format for the scene file:",
                "FILE: <the exact story/chapters path listed under Writes in the current task>",
                "---CONTENT---",
                "<complete scene prose>",
                "---END---",
                "Do not use markdown code fences for prose scene output.",
            ]
        )
    state_paths = {
        "story/plot-state.md",
        "story/characters.md",
        "story/timeline.md",
        "story/unresolved-threads.md",
    }
    if set(normalized).issubset(state_paths) and normalized:
        return "\n".join(
            [
                "Use exactly this delimiter format for each state file you update:",
                "FILE: story/plot-state.md",
                "---CONTENT---",
                "<complete updated state file>",
                "---END---",
                "Do not use markdown code fences for state update output.",
            ]
        )
    return "\n".join(
        [
            "Use one fenced block per file with this exact opening form:",
            "```file:path/inside/project.ext",
            "<complete file content>",
            "```",
            "Alternatively, use FILE: path with ---CONTENT--- and ---END--- delimiters.",
        ]
    )


def _format_allowed_file_writer_paths(allowed_paths: tuple[str, ...]) -> str:
    if not allowed_paths:
        return "Use real project-relative paths, not placeholder paths."
    normalized = tuple(path.replace("\\", "/").rstrip("/") for path in allowed_paths)
    paths = ", ".join(f"`{path}`" for path in allowed_paths)
    guidance = f"Use only paths under these project-relative targets: {paths}."
    if normalized == ("story/chapters",):
        return (
            guidance
            + " This is the drafting stage: write only scene prose; do not update plot state, "
            "characters, timeline, unresolved threads, or other story state files."
        )
    state_paths = {
        "story/plot-state.md",
        "story/characters.md",
        "story/timeline.md",
        "story/unresolved-threads.md",
    }
    if set(normalized).issubset(state_paths):
        return guidance + " This is the state update stage: do not write or rewrite chapter prose."
    return guidance


def parse_review_output(output: str) -> tuple[StageStatus, str, str | None, str | None]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip().lower()] = value.strip()

    raw_status = values.get("status", "")
    if raw_status not in {"pass", "fail", "retry", "escalate"}:
        return "fail", "Review output did not include a valid status.", None, None

    reason = values.get("reason") or "Review returned no reason."
    next_stage = _optional_review_value(values.get("next_stage"))
    context_update = _optional_review_value(values.get("context_update"))
    return raw_status, reason, next_stage, context_update  # type: ignore[return-value]


def _optional_review_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() in {"none", "null", "n/a"}:
        return None
    return normalized


def format_agent_invocation(stage_id: str, invocation: AgentInvocation) -> str:
    stdout = _coerce_output(invocation.stdout)
    stderr = _coerce_output(invocation.stderr)
    prompt = _coerce_output(invocation.prompt)
    return "\n".join(
        [
            f"# Agent Output: {stage_id}",
            "",
            f"Agent: `{invocation.agent_id}`",
            f"Command: `{invocation.command}`",
            f"Exit code: {invocation.exit_code}",
            f"Duration seconds: {invocation.duration_seconds:.3f}",
            f"Timed out: {str(invocation.timed_out).lower()}",
            "",
            "## stdout",
            "",
            "```text",
            stdout.rstrip(),
            "```",
            "",
            "## stderr",
            "",
            "```text",
            stderr.rstrip(),
            "```",
            "",
            "## Prompt",
            "",
            "```markdown",
            prompt.rstrip(),
            "```",
            "",
        ]
    )


def format_agent_invocation_json(stage_id: str, invocation: AgentInvocation) -> str:
    data = {
        **asdict(invocation),
        "stage_id": stage_id,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _agent_invocation_json_filename(output_filename: str) -> str:
    path = Path(output_filename)
    if path.suffix:
        return path.with_suffix(".json").as_posix()
    return path.with_name(path.name + ".json").as_posix()
