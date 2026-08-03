"""Conversions between the internal swim types and their protobuf wire
representation."""

from __future__ import annotations

from dssd import spinepb
from dssd.swim import Event, EventType, Member, State

_STATE_TO_PB = {
    State.ALIVE: spinepb.ALIVE,
    State.SUSPECT: spinepb.SUSPECT,
    State.DEAD: spinepb.DEAD,
}

_EVENT_TYPE_TO_PB = {
    EventType.JOINED: spinepb.JOINED,
    EventType.LEFT: spinepb.LEFT,
    EventType.FAILED: spinepb.FAILED,
    EventType.RECOVERED: spinepb.RECOVERED,
}


def to_pb_member(member: Member) -> spinepb.Member:
    return spinepb.Member(
        id=member.id,
        addr=member.addr,
        state=_STATE_TO_PB[member.state],
        incarnation=member.incarnation,
    )


def to_pb_members(members: list[Member]) -> list[spinepb.Member]:
    return [to_pb_member(m) for m in members]


def to_pb_event(event: Event) -> spinepb.MembershipEvent:
    return spinepb.MembershipEvent(type=_EVENT_TYPE_TO_PB[event.type], member=to_pb_member(event.member))
