"""The leader-side DiLoCo outer-step barrier, exposed over gRPC.

Workers call Sync with their local pseudo-gradient and block until the
round closes: either every currently-alive member (per the membership
spine's quorum) has submitted, or round_timeout elapses with whatever
partial set has submitted. The timeout path is what lets training
continue without a restart when a worker dies mid-round.

This class deliberately doesn't fence stale submissions across leader
changes - a fresh leader always starts its own round counter at 0, so
"round" alone can't distinguish a stale submission from a legitimate new
one. That fencing belongs one layer up, keyed on the Raft term (see
worker.LeaderGatedTrainerService), since a new instance of this class is
constructed per term anyway.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import torch

from dssd import trainerpb

from .outer import OuterOptimizer, StateDict, average_pseudo_gradients

GetQuorum = Callable[[], Awaitable[list[str]]]


def state_to_pb(state: StateDict) -> list[trainerpb.Tensor]:
    return [
        trainerpb.Tensor(key=key, shape=list(value.shape), data=value.flatten().tolist())
        for key, value in state.items()
    ]


def state_from_pb(tensors: list[trainerpb.Tensor]) -> StateDict:
    return {t.key: torch.tensor(list(t.data), dtype=torch.float32).reshape(list(t.shape)) for t in tensors}


class TrainerService(trainerpb.TrainerServicer):
    def __init__(
        self,
        get_quorum: GetQuorum,
        initial_global_state: StateDict,
        lr: float = 0.7,
        momentum: float = 0.9,
        nesterov: bool = True,
        round_timeout: float = 10.0,
    ) -> None:
        self._get_quorum = get_quorum
        self._outer = OuterOptimizer(initial_global_state, lr=lr, momentum=momentum, nesterov=nesterov)
        self._global_state = {k: v.clone() for k, v in initial_global_state.items()}
        self._round = 0
        self._round_timeout = round_timeout

        self._pending: dict[str, StateDict] = {}
        self._round_done = asyncio.Event()
        self._lock = asyncio.Lock()
        self._timeout_task: asyncio.Task | None = None

    async def Sync(self, request: trainerpb.SyncRequest, context) -> trainerpb.SyncResponse:
        pseudo_grad = state_from_pb(request.pseudo_gradient)

        async with self._lock:
            self._pending[request.worker_id] = pseudo_grad
            if self._timeout_task is None:
                self._timeout_task = asyncio.create_task(self._finalize_after_timeout())
            # Capture the event before finalizing, since a finalize
            # triggered by this very call swaps self._round_done to a
            # fresh one for the *next* round - waiting on the attribute
            # read after finalize would deadlock on our own submission.
            wait_event = self._round_done
            await self._maybe_finalize_locked()

        await wait_event.wait()
        return trainerpb.SyncResponse(round=self._round, global_state=state_to_pb(self._global_state))

    async def _maybe_finalize_locked(self) -> None:
        alive = set(await self._get_quorum())
        if alive and alive.issubset(self._pending.keys()):
            self._finalize_locked()

    async def _finalize_after_timeout(self) -> None:
        try:
            await asyncio.sleep(self._round_timeout)
        except asyncio.CancelledError:
            return
        async with self._lock:
            if self._pending:
                self._finalize_locked()

    def _finalize_locked(self) -> None:
        avg = average_pseudo_gradients(list(self._pending.values()))
        self._global_state = self._outer.step(avg)
        self._round += 1
        self._pending = {}
        if self._timeout_task is not None:
            self._timeout_task.cancel()
            self._timeout_task = None

        done = self._round_done
        self._round_done = asyncio.Event()
        done.set()
