from __future__ import annotations

from .models import RunStatus


ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.RUNNING: {RunStatus.SUCCEEDED, RunStatus.PARTIAL_FAILED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.PARTIAL_FAILED: {RunStatus.RUNNING, RunStatus.SUCCEEDED, RunStatus.CANCELLED},
    RunStatus.FAILED: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.SUCCEEDED: set(),
    RunStatus.CANCELLED: set(),
}


def assert_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid status transition: {current} -> {target}")
