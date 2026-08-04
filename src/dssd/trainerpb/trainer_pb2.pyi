from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Tensor(_message.Message):
    __slots__ = ("key", "shape", "data")
    KEY_FIELD_NUMBER: _ClassVar[int]
    SHAPE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    key: str
    shape: _containers.RepeatedScalarFieldContainer[int]
    data: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, key: _Optional[str] = ..., shape: _Optional[_Iterable[int]] = ..., data: _Optional[_Iterable[float]] = ...) -> None: ...

class SyncRequest(_message.Message):
    __slots__ = ("worker_id", "round", "pseudo_gradient")
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    ROUND_FIELD_NUMBER: _ClassVar[int]
    PSEUDO_GRADIENT_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    round: int
    pseudo_gradient: _containers.RepeatedCompositeFieldContainer[Tensor]
    def __init__(self, worker_id: _Optional[str] = ..., round: _Optional[int] = ..., pseudo_gradient: _Optional[_Iterable[_Union[Tensor, _Mapping]]] = ...) -> None: ...

class SyncResponse(_message.Message):
    __slots__ = ("round", "global_state")
    ROUND_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_STATE_FIELD_NUMBER: _ClassVar[int]
    round: int
    global_state: _containers.RepeatedCompositeFieldContainer[Tensor]
    def __init__(self, round: _Optional[int] = ..., global_state: _Optional[_Iterable[_Union[Tensor, _Mapping]]] = ...) -> None: ...
