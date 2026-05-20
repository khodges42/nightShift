"""Retry churn detection and escalation policy helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .retry_memory import RetryMemoryEntry


@dataclass(frozen=True)
class EscalationDecision:
    should_stop: bool
    action: str
    reason: str


def evaluate_retry_churn(entries: tuple[RetryMemoryEntry, ...], *, retry_budget: int) -> EscalationDecision:
    if len(entries) < 2:
        return EscalationDecision(False, "continue", "Not enough retry history for churn detection.")
    recent = entries[-3:]
    same_stage = len({entry.stage_id for entry in recent}) == 1
    same_cause = len({entry.cause for entry in recent}) == 1
    if len(entries) >= retry_budget and retry_budget > 0:
        return EscalationDecision(True, "human review", "Configured retry budget is exhausted.")
    if len(recent) == 3 and same_stage and same_cause:
        return EscalationDecision(True, "debugger review or larger model", "The same stage is failing with the same reason repeatedly.")
    return EscalationDecision(False, "continue", "No retry churn detected.")


def format_escalation_decision(decision: EscalationDecision) -> str:
    return "\n".join(
        [
            "# Escalation Policy",
            "",
            f"Action: {decision.action}",
            f"Stop retries: {str(decision.should_stop).lower()}",
            f"Reason: {decision.reason}",
            "",
        ]
    )
