"""Lightweight repository semantic index."""

from __future__ import annotations

from dataclasses import dataclass
import ast
from pathlib import Path
import re

from .config import SafetyConfig
from .safety import resolve_project_root, validate_scoped_paths


@dataclass(frozen=True)
class IndexedFile:
    path: str
    symbols: tuple[str, ...]
    imports: tuple[str, ...]
    tests: tuple[str, ...]
    keywords: tuple[str, ...]
    snippet: str


def build_semantic_index(project_root: str | Path, safety: SafetyConfig, *, max_files: int = 120) -> tuple[IndexedFile, ...]:
    root = resolve_project_root(project_root)
    scoped_roots = validate_scoped_paths(root, safety.scoped_paths or (".",))
    files: list[IndexedFile] = []
    for scoped_root in scoped_roots:
        for path in sorted(scoped_root.rglob("*")):
            if len(files) >= max_files:
                return tuple(files)
            if not path.is_file() or _skip(path, root):
                continue
            relative = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            files.append(_index_file(relative, text))
    return tuple(files)


def search_index(index: tuple[IndexedFile, ...], query: str, *, limit: int = 5) -> tuple[IndexedFile, ...]:
    query_terms = _keywords(query)
    scored: list[tuple[int, IndexedFile]] = []
    for item in index:
        haystack = set(item.keywords) | set(_keywords(item.path)) | set(_keywords(" ".join(item.symbols + item.imports + item.tests)))
        score = sum(3 if term in item.symbols or term in item.tests else 1 for term in query_terms if term in haystack)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].path))
    return tuple(item for _, item in scored[:limit])


def format_semantic_index(index: tuple[IndexedFile, ...]) -> str:
    lines = ["# Semantic Index", "", f"Files indexed: {len(index)}", ""]
    for item in index:
        lines.extend(
            [
                f"## `{item.path}`",
                "",
                f"- Symbols: {', '.join(item.symbols) or 'None'}",
                f"- Imports: {', '.join(item.imports) or 'None'}",
                f"- Tests: {', '.join(item.tests) or 'None'}",
                "",
                "```text",
                item.snippet,
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def format_search_results(results: tuple[IndexedFile, ...], query: str) -> str:
    lines = ["# Semantic Context", "", f"Query: {query}", ""]
    if not results:
        lines.append("- No matching files.")
        lines.append("")
        return "\n".join(lines)
    for item in results:
        lines.extend(
            [
                f"## `{item.path}`",
                "",
                f"- Symbols: {', '.join(item.symbols) or 'None'}",
                f"- Tests: {', '.join(item.tests) or 'None'}",
                "",
                "```text",
                item.snippet,
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _index_file(path: str, text: str) -> IndexedFile:
    symbols: list[str] = []
    imports: list[str] = []
    tests: list[str] = []
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.append(node.name)
                    if node.name.startswith("test_"):
                        tests.append(node.name)
                elif isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module.split(".")[0])
    return IndexedFile(
        path=path,
        symbols=tuple(_dedupe(symbols)),
        imports=tuple(_dedupe(imports)),
        tests=tuple(_dedupe(tests)),
        keywords=tuple(_keywords(text + " " + path)),
        snippet="\n".join(text.splitlines()[:40]),
    )


def _skip(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    parts = set(Path(relative).parts)
    if parts & {".git", ".nightshift", "__pycache__", ".venv", "venv", "integ_runs"}:
        return True
    if any(part.endswith(".egg-info") for part in parts):
        return True
    return path.suffix.lower() not in {".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".html", ".css", ".js"}


def _keywords(text: str) -> tuple[str, ...]:
    expanded = re.sub(r"[_\d]+", " ", text)
    words = list(re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text))
    words.extend(re.findall(r"[A-Za-z][A-Za-z]{1,}", expanded))
    return tuple(_dedupe(word.lower() for word in words))


def _dedupe(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
