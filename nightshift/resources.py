"""Structured blocked/resource request handling."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3

from .artifacts import ArtifactStore
from .errors import PipelineError


SUPPORTED_RESOURCE_TYPES = {"png", "jpg", "jpeg", "json", "sqlite", "text", "blob"}


@dataclass(frozen=True)
class ResourceRequest:
    kind: str
    path: str
    reason: str = ""


def parse_resource_requests(text: str) -> tuple[ResourceRequest, ...]:
    """Parse simple blocked/resource requests from agent stdout."""

    requests: list[ResourceRequest] = []
    for match in re.finditer(
        r"blocked_request:\s*(?P<kind>[A-Za-z0-9_-]+)\s+(?P<path>[^\s]+)(?:\s+(?P<reason>.*))?",
        text,
        flags=re.IGNORECASE,
    ):
        requests.append(
            ResourceRequest(
                kind=match.group("kind").lower(),
                path=match.group("path").strip(),
                reason=(match.group("reason") or "").strip(),
            )
        )
    return tuple(requests)


def satisfy_resource_requests(artifacts: ArtifactStore, task_id: str, requests: tuple[ResourceRequest, ...]) -> tuple[Path, ...]:
    written: list[Path] = []
    base = artifacts.create_task_dir(task_id).directory / "resources"
    base.mkdir(parents=True, exist_ok=True)
    for request in requests:
        kind = request.kind.lower()
        if kind not in SUPPORTED_RESOURCE_TYPES:
            raise PipelineError(f"Blocked resource request has unsupported type '{request.kind}'.")
        safe_name = _safe_relative_path(request.path)
        target = base / safe_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "json":
            target.write_text(json.dumps({"generated_by": "nightshift", "reason": request.reason}, indent=2) + "\n", encoding="utf-8")
        elif kind == "sqlite":
            with sqlite3.connect(target) as connection:
                connection.execute("create table if not exists nightshift_fixture (id integer primary key, value text)")
                connection.execute("insert into nightshift_fixture(value) values (?)", ("generated",))
        elif kind in {"text", "blob"}:
            target.write_text(request.reason or "generated fixture\n", encoding="utf-8")
        else:
            target.write_bytes(_tiny_image_bytes(kind))
        written.append(target)
    return tuple(written)


def format_resource_report(requests: tuple[ResourceRequest, ...], paths: tuple[Path, ...], root: Path) -> str:
    lines = ["# Resource Requests", ""]
    for request, path in zip(requests, paths):
        lines.extend(
            [
                f"- Type: {request.kind}",
                f"  Path: `{path.relative_to(root).as_posix()}`",
                f"  Reason: {request.reason}",
            ]
        )
    if not requests:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _safe_relative_path(path_text: str) -> Path:
    path = Path(path_text.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise PipelineError(f"Blocked resource request has unsafe path '{path_text}'.")
    return path


def _tiny_image_bytes(kind: str) -> bytes:
    if kind in {"jpg", "jpeg"}:
        return bytes.fromhex("ffd8ffe000104a46494600010101000100010000ffdb004300" + "08" * 64 + "ffc00011080001000103012200021101031101ffc40014000100000000000000000000000000000000000000ffc40014100100000000000000000000000000000000000000ffda000c03010002110311003f00d2cf20ffd9")
    return bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082")
