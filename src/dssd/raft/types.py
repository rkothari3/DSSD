"""Wire-level types for Raft's RequestVote and AppendEntries RPCs, and
the Transport protocol used to send them to peers without depending on
any particular RPC framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LogEntry:
    """One entry in the replicated log. Index 0 is a sentinel; real
    entries start at index 1."""

    term: int
    index: int
    command: bytes


@dataclass(frozen=True)
class ApplyMsg:
    """Delivered for each log entry once committed by a majority of the cluster."""

    index: int
    term: int
    command: bytes


@dataclass(frozen=True)
class RequestVoteArgs:
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


@dataclass(frozen=True)
class RequestVoteReply:
    term: int
    vote_granted: bool


@dataclass(frozen=True)
class AppendEntriesArgs:
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: tuple[LogEntry, ...]
    leader_commit: int


@dataclass(frozen=True)
class AppendEntriesReply:
    term: int
    success: bool


class Transport(Protocol):
    """Lets a Raft instance call RequestVote/AppendEntries on a peer.
    Production code backs this with gRPC; tests back it with an
    in-memory fake."""

    async def request_vote(self, peer_id: str, args: RequestVoteArgs) -> RequestVoteReply: ...

    async def append_entries(self, peer_id: str, args: AppendEntriesArgs) -> AppendEntriesReply: ...
