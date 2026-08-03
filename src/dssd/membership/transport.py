"""A raft.Transport implementation backed by gRPC connections to peers
named by a static id -> address table."""

from __future__ import annotations

import grpc

from dssd import spinepb
from dssd.raft import AppendEntriesArgs, AppendEntriesReply, RequestVoteArgs, RequestVoteReply


class GRPCTransport:
    def __init__(self, addrs: dict[str, str]) -> None:
        self._addrs = addrs
        self._channels: dict[str, grpc.aio.Channel] = {}

    def _stub(self, peer_id: str) -> spinepb.RaftStub:
        channel = self._channels.get(peer_id)
        if channel is None:
            addr = self._addrs.get(peer_id)
            if addr is None:
                raise ValueError(f"membership: unknown raft peer {peer_id!r}")
            channel = grpc.aio.insecure_channel(addr)
            self._channels[peer_id] = channel
        return spinepb.RaftStub(channel)

    async def request_vote(self, peer_id: str, args: RequestVoteArgs) -> RequestVoteReply:
        reply = await self._stub(peer_id).RequestVote(
            spinepb.RequestVoteArgs(
                term=args.term,
                candidate_id=args.candidate_id,
                last_log_index=args.last_log_index,
                last_log_term=args.last_log_term,
            )
        )
        return RequestVoteReply(term=reply.term, vote_granted=reply.vote_granted)

    async def append_entries(self, peer_id: str, args: AppendEntriesArgs) -> AppendEntriesReply:
        reply = await self._stub(peer_id).AppendEntries(
            spinepb.AppendEntriesArgs(
                term=args.term,
                leader_id=args.leader_id,
                prev_log_index=args.prev_log_index,
                prev_log_term=args.prev_log_term,
                entries=[spinepb.LogEntry(term=e.term, index=e.index, command=e.command) for e in args.entries],
                leader_commit=args.leader_commit,
            )
        )
        return AppendEntriesReply(term=reply.term, success=reply.success)

    async def close(self) -> None:
        for channel in self._channels.values():
            await channel.close()
