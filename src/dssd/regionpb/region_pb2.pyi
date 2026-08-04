from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ShardVoteRequest(_message.Message):
    __slots__ = ("shard_id", "term", "candidate_id", "last_log_index", "last_log_term")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    CANDIDATE_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    shard_id: str
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int
    def __init__(self, shard_id: _Optional[str] = ..., term: _Optional[int] = ..., candidate_id: _Optional[str] = ..., last_log_index: _Optional[int] = ..., last_log_term: _Optional[int] = ...) -> None: ...

class ShardVoteReply(_message.Message):
    __slots__ = ("term", "vote_granted")
    TERM_FIELD_NUMBER: _ClassVar[int]
    VOTE_GRANTED_FIELD_NUMBER: _ClassVar[int]
    term: int
    vote_granted: bool
    def __init__(self, term: _Optional[int] = ..., vote_granted: _Optional[bool] = ...) -> None: ...

class ShardLogEntry(_message.Message):
    __slots__ = ("term", "index", "command")
    TERM_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    term: int
    index: int
    command: bytes
    def __init__(self, term: _Optional[int] = ..., index: _Optional[int] = ..., command: _Optional[bytes] = ...) -> None: ...

class ShardAppendRequest(_message.Message):
    __slots__ = ("shard_id", "term", "leader_id", "prev_log_index", "prev_log_term", "entries", "leader_commit")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    LEADER_COMMIT_FIELD_NUMBER: _ClassVar[int]
    shard_id: str
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: _containers.RepeatedCompositeFieldContainer[ShardLogEntry]
    leader_commit: int
    def __init__(self, shard_id: _Optional[str] = ..., term: _Optional[int] = ..., leader_id: _Optional[str] = ..., prev_log_index: _Optional[int] = ..., prev_log_term: _Optional[int] = ..., entries: _Optional[_Iterable[_Union[ShardLogEntry, _Mapping]]] = ..., leader_commit: _Optional[int] = ...) -> None: ...

class ShardAppendReply(_message.Message):
    __slots__ = ("term", "success")
    TERM_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    term: int
    success: bool
    def __init__(self, term: _Optional[int] = ..., success: _Optional[bool] = ...) -> None: ...

class AgentState(_message.Message):
    __slots__ = ("id", "x", "y", "vx", "vy")
    ID_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    VX_FIELD_NUMBER: _ClassVar[int]
    VY_FIELD_NUMBER: _ClassVar[int]
    id: str
    x: float
    y: float
    vx: float
    vy: float
    def __init__(self, id: _Optional[str] = ..., x: _Optional[float] = ..., y: _Optional[float] = ..., vx: _Optional[float] = ..., vy: _Optional[float] = ...) -> None: ...

class HandOffRequest(_message.Message):
    __slots__ = ("shard_id", "term", "agent")
    SHARD_ID_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    AGENT_FIELD_NUMBER: _ClassVar[int]
    shard_id: str
    term: int
    agent: AgentState
    def __init__(self, shard_id: _Optional[str] = ..., term: _Optional[int] = ..., agent: _Optional[_Union[AgentState, _Mapping]] = ...) -> None: ...

class HandOffResponse(_message.Message):
    __slots__ = ("accepted", "reason")
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    reason: str
    def __init__(self, accepted: _Optional[bool] = ..., reason: _Optional[str] = ...) -> None: ...
