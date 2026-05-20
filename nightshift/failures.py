"""Deterministic failure classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re


FAILURE_CATEGORIES = (
    "syntax/import error",
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

    if re.search(r"\b(syntaxerror|indentationerror|importerror)\b", text, re.IGNORECASE):
        return FailureClassification(
            "syntax/import error",
            "Python failed while parsing or importing code.",
            0.86,
            "Send the failure excerpt and touched files back to the implementer.",
            "retry implementation",
            failing_tests,
        )
    missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", text, re.IGNORECASE)
    if not missing:
        missing = re.search(r"ModuleNotFoundError:\s*['\"]?([A-Za-z0-9_.-]+)", text, re.IGNORECASE)
    if missing:
        package = missing.group(1) or "unknown package"
        return FailureClassification(
            "missing dependency",
            f"Runtime cannot import required package `{package}`.",
            0.91,
            "Run dependency diagnostics before another implementation retry.",
            "do not retry implementation until dependency is resolved",
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
