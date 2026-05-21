"""Deterministic failure classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re


FAILURE_CATEGORIES = (
    "syntax/import error",
    "local import mismatch",
    "missing dependency",
    "missing resource/fixture",
    "environment/config issue",
    "API misuse",
    "test expectation mismatch",
    "logic bug",
    "stuck/unclear",
)


@dataclass(frozen=True)
class FailureClassification:
    category: str
    probable_root_cause: str
    confidence: float
    recommended_next_action: str
    retry_recommendation: str
    failing_tests: tuple[str, ...] = ()


def classify_failure(output: str, exit_code: int | None = None, modified_files: tuple[str, ...] = ()) -> FailureClassification:
    """Classify command/test output with deterministic rules."""

    text = output or ""
    lowered = text.lower()
    failing_tests = extract_failing_tests(text)
    exception_name = _extract_exception_name(text)
    source_path, _ = _extract_traceback_location(text)

    if re.search(r"\bno tests ran\b", text, re.IGNORECASE) or exit_code == 5:
        return FailureClassification(
            "test expectation mismatch",
            "Pytest did not collect any tests; generated changes likely removed, renamed, or invalidated the test suite.",
            0.84,
            "Restore the expected tests or block the stage from editing test files.",
            "repair test files or reject the patch that removed tests",
            failing_tests,
        )

    missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", text, re.IGNORECASE)
    if not missing:
        missing = re.search(r"ModuleNotFoundError:\s*['\"]?([A-Za-z0-9_.-]+)", text, re.IGNORECASE)
    if missing:
        package = missing.group(1) or "unknown package"
        if _looks_like_local_module_name(package):
            return FailureClassification(
                "local import mismatch",
                f"Generated code imports local module `{package}` that does not match the project package layout.",
                0.88,
                "Repair imports to use the configured package path or package-relative imports.",
                "retry the stage that introduced the bad import",
                failing_tests,
            )
        return FailureClassification(
            "missing dependency",
            f"Runtime cannot import required package `{package}`.",
            0.91,
            "Run dependency diagnostics before another implementation retry.",
            "do not retry implementation until dependency is resolved",
            failing_tests,
        )
    if exception_name and source_path and _looks_like_project_source(source_path):
        if exception_name in {"TypeError", "AttributeError"}:
            return FailureClassification(
                "API misuse",
                f"The implementation is calling an API with an incompatible shape near `{source_path}`.",
                0.82,
                "Retry implementation with the exception and relevant call site.",
                "retry implementation",
                failing_tests,
            )
        if exception_name in {"NameError", "OperationalError", "KeyError", "ValueError", "IndexError"}:
            return FailureClassification(
                "logic bug",
                f"The failure originates in project code near `{source_path}`.",
                0.8,
                "Send the traceback and touched files back to the implementer.",
                "retry implementation",
                failing_tests,
            )
    if re.search(r"\b(syntaxerror|indentationerror|importerror)\b", text, re.IGNORECASE):
        return FailureClassification(
            "syntax/import error",
            "Python failed while parsing or importing code.",
            0.86,
            "Send the failure excerpt and touched files back to the implementer.",
            "retry implementation",
            failing_tests,
        )
    if any(marker in lowered for marker in ("filenotfounderror", "no such file or directory", "missing fixture", "fixture")):
        return FailureClassification(
            "missing resource/fixture",
            "The run appears to depend on a fixture or resource that is not present.",
            0.78,
            "Generate or request the missing fixture, then rerun validation.",
            "retry after resource remediation",
            failing_tests,
        )
    if any(marker in lowered for marker in ("permission denied", "environment variable", "config error", "not configured", "connection refused")):
        return FailureClassification(
            "environment/config issue",
            "The execution environment or configuration is invalid.",
            0.76,
            "Surface remediation guidance and stop implementation retries.",
            "do not retry implementation",
            failing_tests,
        )
    if any(marker in lowered for marker in ("typeerror", "attributeerror", "unexpected keyword", "has no attribute")):
        return FailureClassification(
            "API misuse",
            "The implementation is calling an API with an incompatible shape.",
            0.72,
            "Retry implementation with the exception and relevant call site.",
            "retry implementation",
            failing_tests,
        )
    if any(marker in lowered for marker in ("assertionerror", "assert ", "expected", " != ", " == ")) or failing_tests:
        return FailureClassification(
            "test expectation mismatch",
            "Tests ran and reported mismatched expected behavior.",
            0.7,
            "Retry implementation with the failing test names and assertion excerpt.",
            "retry implementation",
            failing_tests,
        )
    if exit_code not in (None, 0):
        category = "logic bug" if modified_files else "stuck/unclear"
        return FailureClassification(
            category,
            "The command failed without a more specific deterministic signature.",
            0.45,
            "Use debugger review or compact failure output before retrying.",
            "retry with debugger guidance",
            failing_tests,
        )
    return FailureClassification(
        "stuck/unclear",
        "No failure signature was found.",
        0.2,
        "Inspect the full stage artifact.",
        "manual review",
        failing_tests,
    )


def build_failure_signature(output: str, reason: str = "") -> str:
    text = "\n".join(part for part in (reason, output) if part)
    command = _extract_command(text)
    exception_name = _extract_exception_name(text)
    source_path, source_line = _extract_traceback_location(text)
    parts = [part for part in (exception_name, source_path, source_line, command) if part]
    return " | ".join(parts) if parts else "unknown-failure"


def extract_failing_tests(output: str) -> tuple[str, ...]:
    tests: list[str] = []
    patterns = (
        r"FAILED\s+([^\s]+::[^\s]+)",
        r"ERROR\s+([^\s]+::[^\s]+)",
        r"def\s+(test_[A-Za-z0-9_]+)\(",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, output):
            name = match.group(1).strip()
            if name not in tests:
                tests.append(name)
    return tuple(tests)


def _extract_exception_name(text: str) -> str:
    candidates = []
    for match in re.finditer(r"(?m)^(?:E\s+)?([A-Za-z0-9_.]+(?:Error|Exception|Warning|NameError|TypeError|AttributeError|KeyError|ValueError|IndexError)):\s*(.*)$", text):
        candidates.append(match.group(1))
    return candidates[-1] if candidates else ""


def _extract_traceback_location(text: str) -> tuple[str, str]:
    candidates: list[tuple[int, str, str]] = []
    for match in re.finditer(r'(?m)^\s*File "([^"]+)", line (\d+), in .+$', text):
        path = match.group(1)
        line = match.group(2)
        candidates.append((_traceback_score(path), path, line))
    for match in re.finditer(r"(?m)^.*?([A-Za-z]:[\\/][^:\n]+?\.py):(\d+):", text):
        path = match.group(1)
        line = match.group(2)
        candidates.append((_traceback_score(path), path, line))
    if not candidates:
        return "", ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, path, line = candidates[0]
    return path, line


def _extract_command(text: str) -> str:
    candidates = []
    for match in re.finditer(r"Command:\s*`([^`]+)`", text):
        candidates.append(match.group(1))
    return candidates[-1] if candidates else ""


def _looks_like_project_source(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/src/" in normalized or "/tests/" in normalized


def _looks_like_local_module_name(name: str) -> bool:
    root = name.split(".")[0].lower()
    return root in {"app", "apps", "model", "models", "route", "routes", "view", "views", "main"}


def _traceback_score(path: str) -> int:
    normalized = path.replace("\\", "/").lower()
    score = 0
    if normalized.endswith(".py"):
        score += 1
    if "/src/" in normalized:
        score += 10
    if "/tests/" in normalized:
        score += 8
    if "/site-packages/" in normalized or "/_pytest/" in normalized:
        score -= 20
    return score


def format_failure_classification(result: FailureClassification, *, exit_code: int | None, modified_files: tuple[str, ...]) -> str:
    files = "\n".join(f"- `{path}`" for path in modified_files) or "- None"
    tests = "\n".join(f"- `{name}`" for name in result.failing_tests) or "- None"
    return "\n".join(
        [
            "# Failure Analysis",
            "",
            f"Failure category: {result.category}",
            f"Probable root cause: {result.probable_root_cause}",
            f"Confidence: {result.confidence:.2f}",
            f"Recommended next action: {result.recommended_next_action}",
            f"Retry recommendation: {result.retry_recommendation}",
            f"Exit code: {exit_code if exit_code is not None else ''}",
            "",
            "## Modified Files",
            "",
            files,
            "",
            "## Failing Tests",
            "",
            tests,
            "",
        ]
    )
