"""Compact retry memory artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from .stages import StageResult


@dataclass(frozen=True)
class RetryMemoryEntry:
    attempt: int
    stage_id: str
    status: str
    cause: str
    next_stage: str
    failure_signature: str


def summarize_retry_memory(entries: tuple[RetryMemoryEntry, ...]) -> str:
    lines = ["# Retry Memory", ""]
    if not entries:
        lines.append("- None")
    for entry in entries[-8:]:
        lines.append(
            f"- Attempt {entry.attempt}: `{entry.stage_id}` returned {entry.status}; "
            f"cause: {entry.cause}; signature: `{entry.failure_signature}`; next: `{entry.next_stage}`"
        )
    lines.append("")
    return "\n".join(lines)


def entry_from_stage(
    attempt: int,
    result: StageResult,
    next_stage: str,
    *,
    failure_signature: str,
) -> RetryMemoryEntry:
    return RetryMemoryEntry(
        attempt=attempt,
        stage_id=result.stage_id,
        status=result.status,
        cause=result.reason,
        next_stage=next_stage,
        failure_signature=failure_signature,
    )
