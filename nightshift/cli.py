"""Command line interface for NightShift."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import validate_config
from .errors import ConfigError, NightShiftError
from .init import available_templates, init_project
from .integ import create_integration_run
from .integ_report import build_integration_report, format_integration_report
from .integ_setup import format_setup_result, setup_python_project
from .integ_test import format_integration_test_result, run_integration_test
from .pipeline import PipelineRunner
from .runlog import RunLogger
from .sandbox_run import format_sandbox_run_result, run_sandbox_project
from .status import build_status, format_status
from .task_tests import check_task_test_files, format_task_test_checks, missing_task_test_paths
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
from .what_happened import build_what_happened


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
        default="status_dots",
        choices=tuple(sorted(HOTDOG_ANIMATIONS)),
        help="Terminal animation to show while the run is active.",
    )
    run_parser.add_argument("--no-animation", action="store_true", help="Disable terminal animation.")

    status_parser = subparsers.add_parser("status", help="Inspect NightShift project status.")
    status_parser.add_argument("--config", default="nightshift.yaml", help="Config file to inspect.")

    happened_parser = subparsers.add_parser(
        "what-happened",
        help="Explain the latest NightShift run from local artifacts.",
    )
    happened_parser.add_argument("--config", default="nightshift.yaml", help="Config file to inspect.")
    happened_parser.add_argument("--run", default="latest", help="Run id to inspect. Defaults to latest.")
    happened_parser.add_argument("--task", help="Task id to inspect. Defaults to the latest task artifact.")

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
    integ_parser.add_argument(
        "--setup",
        action="store_true",
        help="Run integ-setup for the generated Python project after creating the sandbox.",
    )
    integ_parser.add_argument(
        "--setup-extra",
        action="append",
        default=["pytest"],
        help="Extra package for --setup. May be repeated. Defaults to pytest.",
    )
    integ_parser.add_argument(
        "--setup-skip-validate",
        action="store_true",
        help="Skip validation during --setup.",
    )
    integ_parser.add_argument(
        "--setup-dry-run",
        action="store_true",
        help="Print --setup commands without running them.",
    )

    integ_test_parser = subparsers.add_parser(
        "integ-test",
        help="Create, set up, validate, and run an integration template task.",
    )
    integ_test_parser.add_argument("--root", default=".", help="Repository root where integ_runs/ is created.")
    integ_test_parser.add_argument(
        "--template",
        default="tutorial-deaddrop",
        choices=available_templates(),
        help="Template to initialize inside the sandbox.",
    )
    integ_test_parser.add_argument("--task", help="Specific task id to run.")
    integ_test_parser.add_argument("--all", action="store_true", help="Run all runnable incomplete tasks.")
    integ_test_parser.add_argument("--keep", type=int, help="Keep only the newest N old integration runs before creating a new one.")
    integ_test_parser.add_argument(
        "--setup-extra",
        action="append",
        default=["pytest"],
        help="Extra package to install during setup. May be repeated. Defaults to pytest.",
    )
    integ_test_parser.add_argument("--setup-skip-validate", action="store_true", help="Skip validation during setup.")
    integ_test_parser.add_argument("--dry-run", action="store_true", help="Print commands without running setup or tasks.")

    sandbox_parser = subparsers.add_parser(
        "sandbox-run",
        help="Copy an existing NightShift project into a sandbox, set it up, and run it.",
    )
    sandbox_parser.add_argument("--project", required=True, help="Existing NightShift project directory to copy.")
    sandbox_output = sandbox_parser.add_mutually_exclusive_group(required=True)
    sandbox_output.add_argument("--output", help="Sandbox output directory. The project is copied to OUTPUT/project.")
    sandbox_output.add_argument(
        "--timestamped",
        action="store_true",
        help="Create a timestamped sandbox under ROOT/integ_runs, like integ-test.",
    )
    sandbox_parser.add_argument("--root", default=".", help="Root used with --timestamped. Defaults to current directory.")
    sandbox_parser.add_argument("--task", help="Specific task id to run.")
    sandbox_parser.add_argument("--all", action="store_true", help="Run all runnable incomplete tasks.")
    sandbox_parser.add_argument("--force", action="store_true", help="Overwrite an existing OUTPUT/project copy.")
    sandbox_parser.add_argument(
        "--setup-extra",
        action="append",
        default=["pytest"],
        help="Extra package to install during setup. May be repeated. Defaults to pytest.",
    )
    sandbox_parser.add_argument("--setup-skip-validate", action="store_true", help="Skip validation during setup.")
    sandbox_parser.add_argument("--dry-run", action="store_true", help="Create the sandbox copy and print commands without running setup or tasks.")
    sandbox_parser.add_argument(
        "--animation",
        default="status_dots",
        choices=tuple(sorted(HOTDOG_ANIMATIONS)),
        help="Terminal animation to show while the sandboxed run is active.",
    )
    sandbox_parser.add_argument("--no-animation", action="store_true", help="Disable terminal animation.")

    integ_report_parser = subparsers.add_parser("integ-report", help="Summarize the latest integration run.")
    integ_report_parser.add_argument("--root", default=".", help="Repository root where integ_runs/ is located.")
    integ_report_parser.add_argument("--latest", action="store_true", help="Report the latest integration run.")

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
            task_test_checks = check_task_test_files(config, tasks)
            missing_task_tests = missing_task_test_paths(task_test_checks)
            if missing_task_tests:
                details = format_task_test_checks(task_test_checks)
                raise ConfigError(f"Config error: missing configured task test files.\n{details}")
            incomplete = sum(1 for task in tasks if not task.completed)
            print(f"Config valid: {config.path}")
            print(f"Project: {config.project.name}")
            print(f"Stages: {len(config.pipeline.stages)}")
            print(f"Tasks: {len(tasks)}")
            print(f"Incomplete tasks: {incomplete}")
            print(format_task_test_checks(task_test_checks))
            return 0

        if args.command == "run":
            config = validate_config(args.config)
            tasks = parse_task_file(config.project.root, config.project.task_file)
            validate_task_dependencies(tasks)
            if args.all and args.task:
                parser.error("run accepts either --all or --task, not both.")
            if args.all:
                with TerminalAnimation(
                    args.animation,
                    message="Starting all tasks",
                    enabled=not args.no_animation,
                ) as animation:
                    runner = PipelineRunner(config, logger=RunLogger(console=animation.emit, status=animation.update_message))
                    result = runner.run_tasks(tasks)
                animation.finish(f"Tasks run: {len(result.task_results)} | Completed: {result.completed_count} | Failed: {result.failed_count}", status=result.status)
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
                message=f"Task: {task.id} | Starting",
                enabled=not args.no_animation,
            ) as animation:
                runner = PipelineRunner(config, logger=RunLogger(console=animation.emit, status=animation.update_message))
                result = runner.run_task(task)
            animation.finish(f"Task: {result.task_id} | Retries: {result.retry_count} | {result.reason}", status=result.status)
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

        if args.command == "what-happened":
            config = validate_config(args.config)
            report = build_what_happened(
                config.project.root,
                config.project.artifact_dir,
                run_id=args.run,
                task_id=args.task,
            )
            print(report.content)
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
            if args.setup:
                result = setup_python_project(
                    run.directory / "project",
                    extras=tuple(args.setup_extra or ()),
                    validate=not args.setup_skip_validate,
                    dry_run=args.setup_dry_run,
                )
                print("")
                print(format_setup_result(result))
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

        if args.command == "integ-test":
            result = run_integration_test(
                args.root,
                template=args.template,
                task=args.task,
                all_tasks=args.all,
                keep=args.keep,
                setup_extras=tuple(args.setup_extra or ()),
                skip_setup_validate=args.setup_skip_validate,
                dry_run=args.dry_run,
            )
            print(format_integration_test_result(result))
            return result.exit_code

        if args.command == "sandbox-run":
            result = run_sandbox_project(
                args.project,
                output=args.output,
                timestamped=args.timestamped,
                root=args.root,
                task=args.task,
                all_tasks=args.all,
                setup_extras=tuple(args.setup_extra or ()),
                skip_setup_validate=args.setup_skip_validate,
                dry_run=args.dry_run,
                animation=args.animation,
                no_animation=args.no_animation,
                force=args.force,
            )
            print(format_sandbox_run_result(result))
            return result.exit_code

        if args.command == "integ-report":
            report = build_integration_report(args.root, latest=True)
            print(format_integration_report(report))
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
