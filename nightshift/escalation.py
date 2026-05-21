"""Retry churn detection and escalation policy helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .retry_memory import RetryMemoryEntry


@dataclass(frozen=True)
class EscalationDecision:
    should_stop: bool
    action: str
    reason: str


def evaluate_retry_churn(
    entries: tuple[RetryMemoryEntry, ...],
    *,
    retry_budget: int,
    repeated_signature_after: int | None = None,
) -> EscalationDecision:
    if len(entries) < 2:
        return EscalationDecision(False, "continue", "Not enough retry history for churn detection.")
    churn_threshold = repeated_signature_after if repeated_signature_after and repeated_signature_after > 0 else 3
    signature_window = entries[-churn_threshold:] if len(entries) >= churn_threshold else ()
    recent_signatures = [entry.failure_signature for entry in signature_window if entry.failure_signature]
    same_signature = len(recent_signatures) == churn_threshold and len(set(recent_signatures)) == 1
    stage_cause_window = entries[-churn_threshold:] if len(entries) >= churn_threshold else ()
    same_stage = bool(stage_cause_window) and len({entry.stage_id for entry in stage_cause_window}) == 1
    same_cause = bool(stage_cause_window) and len({entry.cause for entry in stage_cause_window}) == 1
    if len(entries) >= retry_budget and retry_budget > 0:
        return EscalationDecision(True, "human review", "Configured retry budget is exhausted.")
    if (
        len(entries) >= churn_threshold
        and same_signature
    ):
        return EscalationDecision(
            True,
            "debugger review or larger model",
            "The same failure signature repeated on consecutive retries.",
        )
    if len(entries) >= churn_threshold and same_stage and same_cause:
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
