"""Gates the DiLoCo outer-step barrier so only the current Raft leader
coordinates a round, fencing submissions by term so a worker still
talking to a since-replaced leader gets rejected instead of corrupting
state - the epoch/fencing pattern needed to avoid a zombie coordinator.
"""

from __future__ import annotations

from typing import Protocol

import grpc

from dssd import trainerpb

from .trainer_service import GetQuorum, TrainerService


class RaftView(Protocol):
    def state(self) -> tuple[int, bool]: ...
    def leader_hint(self) -> tuple[str, int]: ...


class LeaderGatedTrainerService(trainerpb.TrainerServicer):
    """A fresh TrainerService is built for each new term, seeded from
    this node's own last-known global state - so a newly elected leader
    (possibly this same node, re-elected) picks up training where the
    group left off instead of resetting it.
    """

    def __init__(self, raft: RaftView, get_quorum: GetQuorum, get_local_state, **outer_kwargs) -> None:
        self._raft = raft
        self._get_quorum = get_quorum
        self._get_local_state = get_local_state
        self._outer_kwargs = outer_kwargs
        self._active: TrainerService | None = None
        self._active_term: int | None = None

    async def Sync(self, request: trainerpb.SyncRequest, context) -> trainerpb.SyncResponse:
        term, is_leader = self._raft.state()
        if not is_leader:
            leader_id, _ = self._raft.leader_hint()
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"not the leader; current leader hint is {leader_id or 'unknown'}",
            )
        if request.term != term:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"stale term: leader is on term {term}, request was for {request.term}",
            )
        if self._active is None or self._active_term != term:
            self._active = TrainerService(self._get_quorum, self._get_local_state(), **self._outer_kwargs)
            self._active_term = term
        return await self._active.Sync(request, context)
