"""Replicates a shard's agent registry through that shard's own Raft
log. Every replica - not just the leader - applies committed entries, so
whichever replica wins the next election already has the full,
up-to-date state and can resume serving immediately: this is what makes
"no agent loss on kill" possible, as opposed to leader-election-only
coordination (which the DiLoCo trainer used, since there the model
state lived with the workers, not the coordinator).
"""

from __future__ import annotations

import asyncio
import json

from dssd import raft

from .world import AgentState


def encode_tick(agents: dict[str, AgentState]) -> bytes:
    return json.dumps(
        [{"id": a.id, "x": a.x, "y": a.y, "vx": a.vx, "vy": a.vy} for a in agents.values()]
    ).encode()


def decode_tick(data: bytes) -> dict[str, AgentState]:
    return {a["id"]: AgentState(**a) for a in json.loads(data)}


class ShardStateMachine:
    """Applies a shard's committed Raft log entries to maintain a
    replicated agent registry, and lets the current leader propose the
    next tick's state."""

    def __init__(self, shard_raft: raft.Raft, apply_queue: "asyncio.Queue[raft.ApplyMsg]") -> None:
        self.raft = shard_raft
        self._apply_queue = apply_queue
        self.agents: dict[str, AgentState] = {}
        self._last_applied_index = 0
        self._apply_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._apply_task = asyncio.create_task(self._apply_loop())

    async def stop(self) -> None:
        if self._apply_task is not None:
            self._apply_task.cancel()
            await asyncio.gather(self._apply_task, return_exceptions=True)

    async def _apply_loop(self) -> None:
        try:
            while True:
                msg = await self._apply_queue.get()
                self.agents = decode_tick(msg.command)
                self._last_applied_index = msg.index
        except asyncio.CancelledError:
            pass

    def propose_tick(self) -> bool:
        """Proposes the current in-memory agent state as the next log
        entry. Only takes effect if this node is still the shard's
        leader; returns whether it was."""
        _, _, is_leader = self.raft.propose(encode_tick(self.agents))
        return is_leader

    async def propose_and_confirm(self, timeout: float = 2.0) -> bool:
        """Proposes the current in-memory agent state and waits for it
        to actually commit, rather than just entering the log. Used
        wherever a caller needs a real durability guarantee (e.g. hand-off)
        instead of best-effort - once this returns True, the state is
        replicated to a majority and will survive this node dying a
        moment later.
        """
        index, term, is_leader = self.raft.propose(encode_tick(self.agents))
        if not is_leader:
            return False

        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            current_term, current_is_leader = self.raft.state()
            if current_term != term or not current_is_leader:
                return False  # superseded before committing
            if self._last_applied_index >= index:
                return True
            await asyncio.sleep(0.01)
        return False
