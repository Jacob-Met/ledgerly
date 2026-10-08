"""Detached presentation of actions already retained by the sandbox agent."""
from collections.abc import Iterable

from ledgerly.agent import PendingAction


def completed_reviews(actions: Iterable[PendingAction]) -> list[dict]:
    """Read recorded outcomes, most recently queued first, without any effects."""
    return [
        action.to_dict()
        for action in reversed(list(actions))
        if action.status in ("APPROVED", "REJECTED", "FAILED")
    ]
