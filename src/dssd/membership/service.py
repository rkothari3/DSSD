"""Exposes a SWIM node and a Raft instance as a single, application-
agnostic gRPC service: the shared spine. Consumers depend only on this
API, never on the SWIM or Raft internals directly.
"""

from __future__ import annotations

import asyncio

import grpc

from dssd import spinepb
from dssd.raft import AppendEntriesArgs as RaftAppendEntriesArgs
from dssd.raft import LogEntry as RaftLogEntry
from dssd.raft import Raft
from dssd.raft import RequestVoteArgs as RaftRequestVoteArgs
from dssd.swim import Event, Node, State

from .convert import to_pb_event, to_pb_members


class Service(spinepb.MembershipServicer, spinepb.RaftServicer):
    def __init__(self, swim_node: Node, raft_node: Raft) -> None:
        self._swim = swim_node
        self._raft = raft_node
        self._view_version = 0
        self._subscribers: dict[int, asyncio.Queue[Event]] = {}
        self._next_sub = 0
        self._fan_out_task: asyncio.Task | None = None

    def start(self) -> None:
        self._fan_out_task = asyncio.create_task(self._fan_out_events())

    async def stop(self) -> None:
        if self._fan_out_task is not None:
            self._fan_out_task.cancel()
            await asyncio.gather(self._fan_out_task, return_exceptions=True)

    async def _fan_out_events(self) -> None:
        try:
            while True:
                event = await self._swim.events.get()
                self._view_version += 1
                for queue in list(self._subscribers.values()):
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        pass  # slow subscriber; drop rather than block
        except asyncio.CancelledError:
            pass

    # --- Membership RPCs ---

    async def Join(self, request, context):
        if not request.id or not request.addr:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "id and addr are required")
        self._swim.learn(request.id, request.addr)
        return spinepb.JoinResponse(members=to_pb_members(self._swim.members()))

    async def Leave(self, request, context):
        if request.id and request.id != self._swim.id:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"a node may only announce its own departure (this is {self._swim.id})",
            )
        self._swim.leave()
        return spinepb.LeaveResponse()

    async def GetMembers(self, request, context):
        return spinepb.GetMembersResponse(members=to_pb_members(self._swim.members()))

    async def GetQuorum(self, request, context):
        alive = [m for m in self._swim.members() if m.state == State.ALIVE]
        return spinepb.GetQuorumResponse(members=to_pb_members(alive), view_version=self._view_version)

    async def GetLeader(self, request, context):
        leader_id, term = self._raft.leader_hint()
        return spinepb.GetLeaderResponse(leader_id=leader_id, term=term)

    async def Watch(self, request, context):
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=32)
        sub_id = self._next_sub
        self._next_sub += 1
        self._subscribers[sub_id] = queue
        try:
            while True:
                event = await queue.get()
                yield to_pb_event(event)
        finally:
            del self._subscribers[sub_id]

    # --- Raft RPCs ---

    async def RequestVote(self, request, context):
        reply = self._raft.handle_request_vote(
            RaftRequestVoteArgs(
                term=request.term,
                candidate_id=request.candidate_id,
                last_log_index=request.last_log_index,
                last_log_term=request.last_log_term,
            )
        )
        return spinepb.RequestVoteReply(term=reply.term, vote_granted=reply.vote_granted)

    async def AppendEntries(self, request, context):
        entries = tuple(
            RaftLogEntry(term=e.term, index=e.index, command=e.command) for e in request.entries
        )
        reply = self._raft.handle_append_entries(
            RaftAppendEntriesArgs(
                term=request.term,
                leader_id=request.leader_id,
                prev_log_index=request.prev_log_index,
                prev_log_term=request.prev_log_term,
                entries=entries,
                leader_commit=request.leader_commit,
            )
        )
        return spinepb.AppendEntriesReply(term=reply.term, success=reply.success)
