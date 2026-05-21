"""Typed NightShift configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .errors import ConfigError
from .errors import SafetyError
from .safety import (
    ensure_command_allowed,
    resolve_inside_root,
    resolve_project_root,
    safe_artifact_path,
    validate_scoped_paths,
)


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    root: Path
    task_file: Path
    artifact_dir: Path


@dataclass(frozen=True)
class SafetyConfig:
    require_clean_worktree: bool
    scoped_paths: tuple[str, ...]
    allowed_commands: tuple[str, ...]
    forbidden_commands: tuple[str, ...]
    allowed_env: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentConfig:
    id: str
    backend: str
    command: str | None
    system_prompt: Path
    model: str | None = None
    role: str | None = None
    temperature: float | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    num_ctx: int | None = None
    num_predict: int | None = None
    seed: int | None = None
    stop: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageConfig:
    id: str
    type: str
    agent: str | None = None
    agent_pool: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    output: str | None = None
    on_fail: str | None = None
    shell: bool = True
    timeout_seconds: int | None = None
    working_dir: Path | None = None
    max_files: int | None = None
    max_lines: int | None = None
    max_delete_ratio: float | None = None
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    mode: str | None = None


@dataclass(frozen=True)
class ExperimentConfig:
    label: str | None = None
    prompt_variant: str | None = None


@dataclass(frozen=True)
class PipelineConfig:
    max_task_retries: int
    stages: tuple[StageConfig, ...]
    continue_on_task_failure: bool = False
    stop_on_repeated_failure_signature_after: int | None = None


@dataclass(frozen=True)
class NightShiftConfig:
    path: Path
    project: ProjectConfig
    safety: SafetyConfig
    agents: dict[str, AgentConfig]
    pipeline: PipelineConfig
    experiment: ExperimentConfig = ExperimentConfig()


AGENT_STAGE_TYPES = {"agent", "agent_review", "review"}
COMMAND_STAGE_TYPES = {"command"}
SUPPORTED_STAGE_TYPES = AGENT_STAGE_TYPES | COMMAND_STAGE_TYPES | {
    "code_writer",
    "file_writer",
    "patch_normalizer",
    "patch_apply",
    "patch_validator",
    "repo_context",
    "semantic_context",
    "summarize",
}


def load_config(path: str | Path = "nightshift.yaml") -> NightShiftConfig:
    """Load and validate a NightShift YAML config file."""

    config_path = Path(path).resolve()
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    raw = _load_yaml_mapping(config_path)
    return parse_config(raw, config_path)


def validate_config(path: str | Path = "nightshift.yaml") -> NightShiftConfig:
    """Load a config and validate referenced local files."""

    config = load_config(path)
    try:
        root = resolve_project_root(config.project.root)
        safe_artifact_path(root, config.project.artifact_dir)
        validate_scoped_paths(root, config.safety.scoped_paths)
    except SafetyError as exc:
        raise ConfigError(str(exc)) from exc

    task_file = resolve_inside_root(root, config.project.task_file, "project.task_file")
    if not task_file.exists():
        raise ConfigError(f"Config error: task file does not exist: {task_file}")

    for agent in config.agents.values():
        prompt = resolve_inside_root(root, agent.system_prompt, f"agents.{agent.id}.system_prompt")
        if not prompt.exists():
            raise ConfigError(
                "Config error: agent "
                f"'{agent.id}' system prompt does not exist: {agent.system_prompt}"
            )

    for stage in config.pipeline.stages:
        if stage.working_dir is not None:
            try:
                resolve_inside_root(root, stage.working_dir, f"stage '{stage.id}' working_dir")
            except SafetyError as exc:
                raise ConfigError(f"Config error: {exc}") from exc
        for command in stage.commands:
            try:
                ensure_command_allowed(
                    command,
                    config.safety.allowed_commands,
                    config.safety.forbidden_commands,
                )
            except SafetyError as exc:
                raise ConfigError(f"Config error: stage '{stage.id}' {exc}") from exc

    return config


def parse_config(raw: dict[str, Any], config_path: Path) -> NightShiftConfig:
    """Convert a raw mapping into typed config objects."""

    _require_mapping(raw, "config")
    for section in ("project", "safety", "agents", "pipeline"):
        if section not in raw:
            raise ConfigError(f"Config error: missing required section '{section}'.")

    project_raw = _require_mapping(raw["project"], "project")
    project_name = _require_string(project_raw, "name", "project")
    project_root_value = _require_string(project_raw, "root", "project")
    project_root = (config_path.parent / project_root_value).resolve()
    project = ProjectConfig(
        name=project_name,
        root=project_root,
        task_file=Path(_require_string(project_raw, "task_file", "project")),
        artifact_dir=Path(_require_string(project_raw, "artifact_dir", "project")),
    )

    safety_raw = _require_mapping(raw["safety"], "safety")
    safety = SafetyConfig(
        require_clean_worktree=_optional_bool(
            safety_raw.get("require_clean_worktree", False),
            "safety.require_clean_worktree",
        ),
        scoped_paths=_string_tuple(safety_raw.get("scoped_paths", []), "safety.scoped_paths"),
        allowed_commands=_string_tuple(safety_raw.get("allowed_commands", []), "safety.allowed_commands"),
        forbidden_commands=_string_tuple(
            safety_raw.get("forbidden_commands", []), "safety.forbidden_commands"
        ),
        allowed_env=_string_tuple(safety_raw.get("allowed_env", []), "safety.allowed_env"),
    )

    agents_raw = _require_mapping(raw["agents"], "agents")
    if not agents_raw:
        raise ConfigError("Config error: at least one agent must be defined.")
    agents: dict[str, AgentConfig] = {}
    for agent_id, agent_raw_value in agents_raw.items():
        agent_raw = _require_mapping(agent_raw_value, f"agents.{agent_id}")
        backend = _require_string(agent_raw, "backend", f"agents.{agent_id}")
        command = _optional_string(agent_raw.get("command"), f"agents.{agent_id}.command")
        model = _optional_string(agent_raw.get("model"), f"agents.{agent_id}.model")
        base_url = _optional_string(agent_raw.get("base_url"), f"agents.{agent_id}.base_url")
        api_key_env = _optional_string(agent_raw.get("api_key_env"), f"agents.{agent_id}.api_key_env")
        temperature = _optional_float_or_none(
            agent_raw.get("temperature"),
            f"agents.{agent_id}.temperature",
        )
        num_ctx = _optional_int_or_none(agent_raw.get("num_ctx"), f"agents.{agent_id}.num_ctx")
        num_predict = _optional_int_or_none(agent_raw.get("num_predict"), f"agents.{agent_id}.num_predict")
        seed = _optional_int_or_none(agent_raw.get("seed"), f"agents.{agent_id}.seed")
        stop = _string_tuple(agent_raw.get("stop", []), f"agents.{agent_id}.stop")
        if temperature is not None and temperature < 0:
            raise ConfigError(
                f"Config error: agents.{agent_id}.temperature must be zero or greater."
            )
        if num_ctx is not None and num_ctx <= 0:
            raise ConfigError(f"Config error: agents.{agent_id}.num_ctx must be greater than zero.")
        if num_predict is not None and num_predict <= 0:
            raise ConfigError(f"Config error: agents.{agent_id}.num_predict must be greater than zero.")
        if backend not in {"command", "ollama", "openai_compatible"}:
            raise ConfigError(
                f"Config error: agent '{agent_id}' uses unsupported backend '{backend}'. "
                "Supported backends: command, ollama, openai_compatible."
            )
        if backend == "command" and command is None:
            raise ConfigError(
                f"Config error: command backend agent '{agent_id}' must define command."
            )
        if backend == "ollama" and model is None:
            raise ConfigError(
                f"Config error: ollama backend agent '{agent_id}' must define model."
            )
        if backend == "openai_compatible" and model is None:
            raise ConfigError(
                f"Config error: openai_compatible backend agent '{agent_id}' must define model."
            )
        if backend == "openai_compatible" and base_url is None:
            raise ConfigError(
                f"Config error: openai_compatible backend agent '{agent_id}' must define base_url."
            )
        system_prompt = Path(_require_string(agent_raw, "system_prompt", f"agents.{agent_id}"))
        agents[str(agent_id)] = AgentConfig(
            id=str(agent_id),
            backend=backend,
            command=command,
            system_prompt=system_prompt,
            model=model,
            role=_optional_string(agent_raw.get("role"), f"agents.{agent_id}.role"),
            temperature=temperature,
            base_url=base_url,
            api_key_env=api_key_env,
            num_ctx=num_ctx,
            num_predict=num_predict,
            seed=seed,
            stop=stop,
        )

    experiment_raw = raw.get("experiment", {})
    if experiment_raw is None:
        experiment_raw = {}
    experiment_raw = _require_mapping(experiment_raw, "experiment")
    experiment = ExperimentConfig(
        label=_optional_string(experiment_raw.get("label"), "experiment.label"),
        prompt_variant=_optional_string(
            experiment_raw.get("prompt_variant"), "experiment.prompt_variant"
        ),
    )

    pipeline_raw = _require_mapping(raw["pipeline"], "pipeline")
    max_task_retries = _optional_int(
        pipeline_raw.get("max_task_retries", 0),
        "pipeline.max_task_retries",
    )
    if max_task_retries < 0:
        raise ConfigError("Config error: pipeline.max_task_retries must be zero or greater.")
    continue_on_task_failure = _optional_bool(
        pipeline_raw.get("continue_on_task_failure", False),
        "pipeline.continue_on_task_failure",
    )
    stop_on_repeated_failure_signature_after = _optional_int_or_none(
        pipeline_raw.get("stop_on_repeated_failure_signature_after"),
        "pipeline.stop_on_repeated_failure_signature_after",
    )
    if stop_on_repeated_failure_signature_after is not None and stop_on_repeated_failure_signature_after < 2:
        raise ConfigError(
            "Config error: pipeline.stop_on_repeated_failure_signature_after must be two or greater."
        )

    stages_raw = pipeline_raw.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ConfigError("Config error: pipeline.stages must be a non-empty list.")

    stages: list[StageConfig] = []
    seen_stage_ids: set[str] = set()
    for index, stage_raw_value in enumerate(stages_raw):
        stage_context = f"pipeline.stages[{index}]"
        stage_raw = _require_mapping(stage_raw_value, stage_context)
        stage_id = _require_string(stage_raw, "id", stage_context)
        if stage_id in seen_stage_ids:
            raise ConfigError(f"Config error: duplicate pipeline stage id '{stage_id}'.")
        seen_stage_ids.add(stage_id)

        stage_type = _require_string(stage_raw, "type", stage_context)
        if stage_type not in SUPPORTED_STAGE_TYPES:
            supported = ", ".join(sorted(SUPPORTED_STAGE_TYPES))
            raise ConfigError(
                f"Config error: stage '{stage_id}' has unsupported type '{stage_type}'. "
                f"Supported types: {supported}."
            )

        agent = _optional_string(stage_raw.get("agent"), f"{stage_context}.agent")
        agent_pool = _string_tuple(stage_raw.get("agent_pool", []), f"{stage_context}.agent_pool")
        commands = _string_tuple(stage_raw.get("commands", []), f"{stage_context}.commands")
        timeout_seconds = _optional_int_or_none(
            stage_raw.get("timeout_seconds"),
            f"{stage_context}.timeout_seconds",
        )
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ConfigError(f"Config error: {stage_context}.timeout_seconds must be greater than zero.")
        working_dir_raw = _optional_string(stage_raw.get("working_dir"), f"{stage_context}.working_dir")
        max_files = _optional_int_or_none(stage_raw.get("max_files"), f"{stage_context}.max_files")
        max_lines = _optional_int_or_none(stage_raw.get("max_lines"), f"{stage_context}.max_lines")
        max_delete_ratio = _optional_float_or_none(
            stage_raw.get("max_delete_ratio"),
            f"{stage_context}.max_delete_ratio",
        )
        if max_files is not None and max_files <= 0:
            raise ConfigError(f"Config error: {stage_context}.max_files must be greater than zero.")
        if max_lines is not None and max_lines <= 0:
            raise ConfigError(f"Config error: {stage_context}.max_lines must be greater than zero.")
        if max_delete_ratio is not None and not 0 <= max_delete_ratio <= 1:
            raise ConfigError(f"Config error: {stage_context}.max_delete_ratio must be between 0 and 1.")
        mode = _optional_string(stage_raw.get("mode"), f"{stage_context}.mode")
        if stage_type == "patch_apply" and mode not in {None, "dry_run", "apply"}:
            raise ConfigError(
                f"Config error: {stage_context}.mode must be 'dry_run' or 'apply'."
            )

        effective_agent = agent or (agent_pool[0] if agent_pool else None)

        if stage_type in AGENT_STAGE_TYPES:
            if effective_agent is None:
                raise ConfigError(f"Config error: agent stage '{stage_id}' must reference an agent.")
            if effective_agent not in agents:
                defined = ", ".join(sorted(agents))
                raise ConfigError(
                    f"Config error: pipeline stage '{stage_id}' references unknown agent "
                    f"'{effective_agent}'. Defined agents: {defined}."
                )
        if stage_type in {"code_writer", "file_writer"}:
            if effective_agent is None:
                raise ConfigError(f"Config error: {stage_type} stage '{stage_id}' must reference an agent.")
            if effective_agent not in agents:
                defined = ", ".join(sorted(agents))
                raise ConfigError(
                    f"Config error: pipeline stage '{stage_id}' references unknown agent "
                    f"'{effective_agent}'. Defined agents: {defined}."
                )
        for pooled_agent in agent_pool:
            if pooled_agent not in agents:
                defined = ", ".join(sorted(agents))
                raise ConfigError(
                    f"Config error: pipeline stage '{stage_id}' references unknown pooled agent "
                    f"'{pooled_agent}'. Defined agents: {defined}."
                )
        if stage_type == "patch_normalizer" and agent is not None and agent not in agents:
            defined = ", ".join(sorted(agents))
            raise ConfigError(
                f"Config error: pipeline stage '{stage_id}' references unknown agent "
                f"'{agent}'. Defined agents: {defined}."
            )

        if stage_type in COMMAND_STAGE_TYPES and not commands:
            raise ConfigError(f"Config error: command stage '{stage_id}' must define commands.")
        if stage_type not in COMMAND_STAGE_TYPES and commands:
            raise ConfigError(
                f"Config error: non-command stage '{stage_id}' must not define commands."
            )

        stages.append(
            StageConfig(
                id=stage_id,
                type=stage_type,
                agent=effective_agent,
                agent_pool=agent_pool,
                commands=commands,
                output=_optional_string(stage_raw.get("output"), f"{stage_context}.output"),
                on_fail=_optional_string(stage_raw.get("on_fail"), f"{stage_context}.on_fail"),
                shell=_optional_bool(stage_raw.get("shell", True), f"{stage_context}.shell"),
                timeout_seconds=timeout_seconds,
                working_dir=Path(working_dir_raw) if working_dir_raw else None,
                max_files=max_files,
                max_lines=max_lines,
                max_delete_ratio=max_delete_ratio,
                allowed_paths=_string_tuple(
                    stage_raw.get("allowed_paths", []),
                    f"{stage_context}.allowed_paths",
                ),
                forbidden_paths=_string_tuple(
                    stage_raw.get("forbidden_paths", []),
                    f"{stage_context}.forbidden_paths",
                ),
                mode=mode,
            )
        )

    stage_ids = {stage.id for stage in stages}
    for stage in stages:
        if stage.on_fail and stage.on_fail not in stage_ids:
            raise ConfigError(
                f"Config error: stage '{stage.id}' on_fail references unknown stage '{stage.on_fail}'."
            )

    return NightShiftConfig(
        path=config_path,
        project=project,
        safety=safety,
        agents=agents,
        pipeline=PipelineConfig(
            max_task_retries=max_task_retries,
            stages=tuple(stages),
            continue_on_task_failure=continue_on_task_failure,
            stop_on_repeated_failure_signature_after=stop_on_repeated_failure_signature_after,
        ),
        experiment=experiment,
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        data = _parse_simple_yaml(text)
    else:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise ConfigError(f"Config error: invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError("Config error: top-level YAML value must be a mapping.")
    return data


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by NightShift starter configs.

    PyYAML is used when available. This fallback keeps `nightshift init` and
    `nightshift validate` usable in a fresh checkout with only the stdlib.
    """

    lines = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        without_comment = raw_line.split("#", 1)[0].rstrip()
        if without_comment.strip():
            indent = len(without_comment) - len(without_comment.lstrip(" "))
            lines.append((line_number, indent, without_comment.strip()))

    index = 0

    def parse_block(expected_indent: int) -> Any:
        nonlocal index
        if index >= len(lines):
            return {}

        _, current_indent, content = lines[index]
        if current_indent < expected_indent:
            return {}
        if current_indent != expected_indent:
            line_number = lines[index][0]
            raise ConfigError(f"Config error: invalid indentation near line {line_number}.")

        if content.startswith("- "):
            sequence: list[Any] = []
            while index < len(lines):
                line_number, indent, item = lines[index]
                if indent < expected_indent:
                    break
                if indent != expected_indent or not item.startswith("- "):
                    break
                item_content = item[2:].strip()
                index += 1
                if not item_content:
                    sequence.append(parse_block(expected_indent + 2))
                elif _looks_like_key_value(item_content):
                    key, value = _split_key_value(item_content, line_number)
                    mapping: dict[str, Any] = {}
                    mapping[key] = (
                        parse_block(expected_indent + 2)
                        if value == ""
                        else _parse_scalar(value)
                    )
                    while index < len(lines):
                        _, child_indent, child_content = lines[index]
                        if child_indent <= expected_indent:
                            break
                        if child_indent != expected_indent + 2:
                            child_line = lines[index][0]
                            raise ConfigError(
                                f"Config error: invalid indentation near line {child_line}."
                            )
                        if child_content.startswith("- "):
                            break
                        child_key, child_value = _split_key_value(child_content, lines[index][0])
                        index += 1
                        mapping[child_key] = (
                            parse_block(expected_indent + 4)
                            if child_value == ""
                            else _parse_scalar(child_value)
                        )
                    sequence.append(mapping)
                else:
                    sequence.append(_parse_scalar(item_content))
            return sequence

        mapping: dict[str, Any] = {}
        while index < len(lines):
            line_number, indent, item = lines[index]
            if indent < expected_indent:
                break
            if indent != expected_indent:
                break
            if item.startswith("- "):
                break
            key, value = _split_key_value(item, line_number)
            index += 1
            mapping[key] = parse_block(expected_indent + 2) if value == "" else _parse_scalar(value)
        return mapping

    parsed = parse_block(0)
    if not isinstance(parsed, dict):
        raise ConfigError("Config error: top-level YAML value must be a mapping.")
    return parsed


def _looks_like_key_value(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_-]+:", value))


def _split_key_value(value: str, line_number: int) -> tuple[str, str]:
    if ":" not in value:
        raise ConfigError(f"Config error: expected key/value pair near line {line_number}.")
    key, raw_value = value.split(":", 1)
    key = key.strip()
    if not key:
        raise ConfigError(f"Config error: empty key near line {line_number}.")
    return key, raw_value.strip()


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(\d+\.\d*|\d*\.\d+)", value):
        return float(value)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"Config error: '{context}' must be a mapping.")
    return value


def _require_string(mapping: dict[str, Any], key: str, context: str) -> str:
    if key not in mapping:
        raise ConfigError(f"Config error: missing required key '{context}.{key}'.")
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise ConfigError(f"Config error: '{context}.{key}' must be a non-empty string.")
    return value


def _optional_string(value: Any, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError(f"Config error: '{context}' must be a non-empty string when set.")
    return value


def _optional_bool(value: Any, context: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"Config error: '{context}' must be a boolean.")


def _optional_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"Config error: '{context}' must be an integer.")
    return value


def _optional_int_or_none(value: Any, context: str) -> int | None:
    if value is None:
        return None
    return _optional_int(value, context)


def _optional_float_or_none(value: Any, context: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"Config error: '{context}' must be a number when set.")
    return float(value)


def _string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ConfigError(f"Config error: '{context}' must be a list of non-empty strings.")
    return tuple(value)
