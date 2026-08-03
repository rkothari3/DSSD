"""SWIM membership state: members, their liveness state, and the
conflict-resolution rule used to reconcile gossiped updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class State(IntEnum):
    """A member's failure-detector state. Values double as a severity
    rank: DEAD > SUSPECT > ALIVE."""

    ALIVE = 0
    SUSPECT = 1
    DEAD = 2


@dataclass(frozen=True)
class Member:
    id: str
    addr: str
    state: State
    incarnation: int = 0


class EventType(IntEnum):
    JOINED = 0
    LEFT = 1
    FAILED = 2
    RECOVERED = 3


@dataclass(frozen=True)
class Event:
    type: EventType
    member: Member


def supersedes(update: Member, current: Member) -> bool:
    """SWIM's conflict-resolution rule: higher incarnation always wins;
    at equal incarnation, more severe state wins; Dead always wins since
    it's terminal regardless of incarnation.
    """
    if update.state == State.DEAD:
        return current.state != State.DEAD
    if update.incarnation > current.incarnation:
        return True
    if update.incarnation == current.incarnation:
        return update.state > current.state
    return False
