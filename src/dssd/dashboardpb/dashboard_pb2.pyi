from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class GetStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetStatusResponse(_message.Message):
    __slots__ = ("worker_id", "round", "loss", "has_loss")
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    LOSS_FIELD_NUMBER: _ClassVar[int]
    HAS_LOSS_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    round: int
    loss: float
    has_loss: bool
    def __init__(self, worker_id: _Optional[str] = ..., round: _Optional[int] = ..., loss: _Optional[float] = ..., has_loss: _Optional[bool] = ...) -> None: ...
