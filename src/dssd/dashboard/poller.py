"""Polls every known worker's status and membership view to build a
single JSON-serializable snapshot for the live dashboard.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass

import grpc

from dssd import dashboardpb, spinepb

_STATE_NAMES = {spinepb.ALIVE: "ALIVE", spinepb.SUSPECT: "SUSPECT", spinepb.DEAD: "DEAD"}


@dataclass
class WorkerSnapshot:
    id: str
    reachable: bool
    state: str = "UNKNOWN"
    round: int = 0
    loss: float | None = None


class Poller:
    """Polls a fixed set of worker addresses directly for their own
    round/loss, and reads the SWIM membership view from whichever one
    answers first.
    """

    def __init__(self, peer_addrs: dict[str, str], timeout: float = 2.0) -> None:
        self._peer_addrs = peer_addrs
        self._timeout = timeout

    async def snapshot(self) -> dict:
        statuses = await asyncio.gather(
            *(self._poll_status(worker_id, addr) for worker_id, addr in self._peer_addrs.items())
        )
        states_by_id = await self._poll_member_states()

        workers = []
        for snap in statuses:
            if snap.id in states_by_id:
                snap.state = states_by_id[snap.id]
            workers.append(asdict(snap))

        return {"timestamp": time.time(), "workers": workers}

    async def _poll_status(self, worker_id: str, addr: str) -> WorkerSnapshot:
        try:
            async with grpc.aio.insecure_channel(addr) as channel:
                stub = dashboardpb.WorkerStatusStub(channel)
                resp = await stub.GetStatus(dashboardpb.GetStatusRequest(), timeout=self._timeout)
            return WorkerSnapshot(
                id=resp.worker_id or worker_id,
                reachable=True,
                round=resp.round,
                loss=resp.loss if resp.has_loss else None,
            )
        except grpc.aio.AioRpcError:
            return WorkerSnapshot(id=worker_id, reachable=False, state="UNREACHABLE")

    async def _poll_member_states(self) -> dict[str, str]:
        for addr in self._peer_addrs.values():
            try:
                async with grpc.aio.insecure_channel(addr) as channel:
                    stub = spinepb.MembershipStub(channel)
                    resp = await stub.GetMembers(spinepb.GetMembersRequest(), timeout=self._timeout)
                return {m.id: _STATE_NAMES.get(m.state, "UNKNOWN") for m in resp.members}
            except grpc.aio.AioRpcError:
                continue
        return {}
