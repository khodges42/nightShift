"""Command line interface for NightShift."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import validate_config
from .errors import NightShiftError
from .init import available_templates, init_project
from .integ import create_integration_run
from .integ_setup import format_setup_result, setup_python_project
from .pipeline import PipelineRunner
from .runlog import RunLogger
from .status import build_status, format_status
from .terminal import HOTDOG_ANIMATIONS, TerminalAnimation, format_banner, style_text
from .tasks import (
    ensure_dependencies_satisfied,
    parse_task_file,
    select_next_runnable_task,
    select_task_by_id,
    validate_task_dependencies,
)
from .version import display_version
from .web import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nightshift", description="Auditable AI pipeline runner.")
    parser.add_argument("--version", action="version", version=f"nightshift {display_version()}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create starter NightShift files.")
    init_parser.add_argument("--root", default=".", help="Directory to initialize.")
    init_parser.add_argument(
        "--template",
        default="basic",
        choices=available_templates(),
        help="Starter template to create.",
    )
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing starter files.")

    validate_parser = subparsers.add_parser("validate", help="Validate nightshift.yaml.")
    validate_parser.add_argument("--config", default="nightshift.yaml", help="Config file to validate.")

    run_parser = subparsers.add_parser("run", help="Run the configured pipeline for one task.")
    run_parser.add_argument("--config", default="nightshift.yaml", help="Config file to use.")
    run_parser.add_argument("--task", help="Specific task id to run.")
    run_parser.add_argument("--all", action="store_true", help="Run all runnable incomplete tasks.")
    run_parser.add_argument(
        "--animation",
        default="agent_thinking",
        choices=tuple(sorted(HOTDOG_ANIMATIONS)),
        help="Terminal animation to show while the run is active.",
    )
    run_parser.add_argument("--no-animation", action="store_true", help="Disable terminal animation.")

    status_parser = subparsers.add_parser("status", help="Inspect NightShift project status.")
    status_parser.add_argument("--config", default="nightshift.yaml", help="Config file to inspect.")

    web_parser = subparsers.add_parser("web", help="Start a read-only artifact dashboard.")
    web_parser.add_argument("--config", default="nightshift.yaml", help="Config file to inspect.")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    web_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")

    integ_parser = subparsers.add_parser("integ-run", help="Create an isolated integration run directory.")
    integ_parser.add_argument("--root", default=".", help="Repository root where integ_runs/ is created.")
    integ_parser.add_argument(
        "--template",
        default="basic",
        choices=available_templates(),
        help="Template to initialize inside the sandbox.",
    )
    integ_parser.add_argument("--keep", type=int, help="Keep only the newest N old integration runs before creating a new one.")

    setup_parser = subparsers.add_parser(
        "integ-setup",
        help="Set up a Python integration project venv and dependencies.",
    )
    setup_parser.add_argument(
        "--project",
        default=".",
        help="Generated project directory. Defaults to the current directory.",
    )
    setup_parser.add_argument(
        "--nightshift-root",
        help="NightShift checkout to install into the integration venv. Defaults to this checkout.",
    )
    setup_parser.add_argument(
        "--extra",
        action="append",
        default=["pytest"],
        help="Extra package to install into the venv. May be repeated. Defaults to pytest.",
    )
    setup_parser.add_argument(
        "--no-create-venv",
        action="store_true",
        help="Fail instead of creating a missing virtual environment.",
    )
    setup_parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip `nightshift validate` after installation.",
    )
    setup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print setup commands without running them.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _emit_banner(args.command)
        if args.command == "init":
            written = init_project(Path(args.root), force=args.force, template=args.template)
            print("Created NightShift starter files:")
            for path in written:
                print(f"- {path}")
            return 0

        if args.command == "validate":
            config = validate_config(args.config)
            tasks = parse_task_file(config.project.root, config.project.task_file)
            validate_task_dependencies(tasks)
            incomplete = sum(1 for task in tasks if not task.completed)
            print(f"Config valid: {config.path}")
            print(f"Project: {config.project.name}")
            print(f"Stages: {len(config.pipeline.stages)}")
            print(f"Tasks: {len(tasks)}")
            print(f"Incomplete tasks: {incomplete}")
            return 0

        if args.command == "run":
            config = validate_config(args.config)
            tasks = parse_task_file(config.project.root, config.project.task_file)
            validate_task_dependencies(tasks)
            if args.all and args.task:
                parser.error("run accepts either --all or --task, not both.")
            runner = PipelineRunner(config, logger=RunLogger(console=print))
            if args.all:
                selected = [task for task in tasks if not task.completed]
                with TerminalAnimation(
                    args.animation,
                    message="NightShift running all tasks",
                    enabled=not args.no_animation,
                ):
                    result = runner.run_tasks(selected)
                print(f"Status: {result.status}")
                print(f"Tasks run: {len(result.task_results)}")
                print(f"Completed: {result.completed_count}")
                print(f"Failed: {result.failed_count}")
                print(f"Reason: {result.reason}")
                return 0 if result.status == "complete" else 1

            task = select_task_by_id(tasks, args.task) if args.task else select_next_runnable_task(tasks)
            ensure_dependencies_satisfied(tasks, task)
            with TerminalAnimation(
                args.animation,
                message=f"NightShift running {task.id}",
                enabled=not args.no_animation,
            ):
                result = runner.run_task(task)
            print(f"Task: {result.task_id}")
            print(style_text(f"Status: {result.status}", color=_status_color(result.status), bold=True))
            print(f"Retries: {result.retry_count}")
            print(f"Artifacts: {result.artifact_dir}")
            print(f"Reason: {result.reason}")
            return 0 if result.status == "complete" else 1

        if args.command == "status":
            config = validate_config(args.config)
            tasks = parse_task_file(config.project.root, config.project.task_file)
            print(format_status(build_status(config, tasks)))
            return 0

        if args.command == "web":
            config = validate_config(args.config)
            app = create_app(config.project.root, config.project.artifact_dir)
            app.run(host=args.host, port=args.port)
            return 0

        if args.command == "integ-run":
            run = create_integration_run(Path(args.root), template=args.template, keep=args.keep)
            print(f"Integration run: {run.directory}")
            print(f"Venv: {run.venv_dir}")
            print(f"Log: {run.log_path}")
            print(f"Setup: python -m nightshift.cli integ-setup --project {run.directory / 'project'}")
            return 0

        if args.command == "integ-setup":
            result = setup_python_project(
                args.project,
                nightshift_root=args.nightshift_root,
                extras=tuple(args.extra or ()),
                create_venv=not args.no_create_venv,
                validate=not args.skip_validate,
                dry_run=args.dry_run,
            )
            print(format_setup_result(result))
            return 0

    except NightShiftError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


def _emit_banner(command: str) -> None:
    if command == "web" or not sys.stdout.isatty():
        return
    print(format_banner())


def _status_color(status: str) -> str | None:
    lowered = status.lower()
    if lowered in {"complete", "pass", "success"}:
        return "\x1b[32m"
    if lowered in {"failed", "fail", "error"}:
        return "\x1b[31m"
    if lowered in {"retry", "blocked", "warning"}:
        return "\x1b[33m"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
