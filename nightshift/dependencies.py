"""Python dependency diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class DependencyDiagnostic:
    missing_imports: tuple[str, ...]
    manifests: tuple[str, ...]
    recommendation: str


def diagnose_python_dependencies(project_root: Path, failure_output: str) -> DependencyDiagnostic:
    imports = []
    for match in re.finditer(r"No module named ['\"]([^'\"]+)['\"]", failure_output):
        name = match.group(1).split(".")[0]
        if name not in imports:
            imports.append(name)
    manifests = tuple(
        relative
        for relative in ("pyproject.toml", "requirements.txt", "poetry.lock", "uv.lock")
        if (project_root / relative).exists()
    )
    if not imports:
        recommendation = "No missing Python import was detected."
    elif "pyproject.toml" in manifests:
        recommendation = "Add the missing package to pyproject.toml, then install with the configured tool."
    elif "requirements.txt" in manifests:
        recommendation = "Add the missing package to requirements.txt, then run pip install -r requirements.txt."
    else:
        recommendation = "Create a Python dependency manifest or install the missing package in the active environment."
    return DependencyDiagnostic(tuple(imports), manifests, recommendation)


def format_dependency_diagnostic(diagnostic: DependencyDiagnostic) -> str:
    imports = "\n".join(f"- `{name}`" for name in diagnostic.missing_imports) or "- None"
    manifests = "\n".join(f"- `{name}`" for name in diagnostic.manifests) or "- None"
    return "\n".join(
        [
            "# Dependency Diagnostic",
            "",
            "## Missing Imports",
            "",
            imports,
            "",
            "## Manifests",
            "",
            manifests,
            "",
            f"Recommendation: {diagnostic.recommendation}",
            "",
        ]
    )
