"""Shared stage result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StageStatus = Literal["pass", "fail", "retry", "escalate"]


@dataclass(frozen=True)
class StageResult:
    stage_id: str
    status: StageStatus
    reason: str
    output_path: str | None = None
    next_stage: str | None = None
    context_update: str | None = None
