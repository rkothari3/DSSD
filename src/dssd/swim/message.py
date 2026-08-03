"""The UDP wire format exchanged between SWIM nodes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from .state import Member, State


class MsgType(str, Enum):
    PING = "ping"
    PING_REQ = "ping-req"
    ACK = "ack"
    JOIN = "join"
    JOIN_ACK = "join-ack"
    GOSSIP = "gossip"  # one-way piggyback push, e.g. a graceful leave


@dataclass(frozen=True)
class Sender:
    """Identifies a message's origin. Its presence is itself a liveness
    assertion: whoever sent this message is alive as of incarnation."""

    id: str = ""
    addr: str = ""
    incarnation: int = 0


@dataclass(frozen=True)
class Message:
    type: MsgType
    seq: int
    sender: Sender = field(default_factory=Sender)
    target_addr: str = ""  # ping-req only
    updates: tuple[Member, ...] = ()

    def encode(self) -> bytes:
        return json.dumps(
            {
                "type": self.type.value,
                "seq": self.seq,
                "sender": {"id": self.sender.id, "addr": self.sender.addr, "incarnation": self.sender.incarnation},
                "target_addr": self.target_addr,
                "updates": [
                    {"id": m.id, "addr": m.addr, "state": int(m.state), "incarnation": m.incarnation}
                    for m in self.updates
                ],
            }
        ).encode()

    @staticmethod
    def decode(data: bytes) -> Message:
        obj = json.loads(data)
        sender = Sender(**obj.get("sender", {}))
        updates = tuple(
            Member(id=u["id"], addr=u["addr"], state=State(u["state"]), incarnation=u["incarnation"])
            for u in obj.get("updates", [])
        )
        return Message(
            type=MsgType(obj["type"]),
            seq=obj["seq"],
            sender=sender,
            target_addr=obj.get("target_addr", ""),
            updates=updates,
        )
