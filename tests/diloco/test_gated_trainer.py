import pytest
import torch

from dssd import trainerpb
from dssd.diloco.gated_trainer import LeaderGatedTrainerService
from dssd.diloco.trainer_service import state_from_pb, state_to_pb


class FakeContext:
    async def abort(self, code, details):
        raise RuntimeError(f"aborted: {code}: {details}")


class FakeRaft:
    def __init__(self, term: int, is_leader: bool, leader_id: str = "") -> None:
        self.term = term
        self.is_leader = is_leader
        self.leader_id = leader_id

    def state(self):
        return self.term, self.is_leader

    def leader_hint(self):
        return self.leader_id, self.term


def make_request(worker_id: str, term: int, pseudo_grad) -> trainerpb.SyncRequest:
    return trainerpb.SyncRequest(worker_id=worker_id, round=0, term=term, pseudo_gradient=state_to_pb(pseudo_grad))


async def test_rejects_when_not_leader():
    raft = FakeRaft(term=1, is_leader=False, leader_id="other")

    async def get_quorum():
        return ["a"]

    service = LeaderGatedTrainerService(
        raft, get_quorum, lambda: {"w": torch.tensor([0.0])}, lr=1.0, momentum=0.0, nesterov=False, round_timeout=5.0
    )

    with pytest.raises(RuntimeError):
        await service.Sync(make_request("a", 1, {"w": torch.tensor([1.0])}), FakeContext())


async def test_rejects_stale_term():
    raft = FakeRaft(term=2, is_leader=True)

    async def get_quorum():
        return ["a"]

    service = LeaderGatedTrainerService(
        raft, get_quorum, lambda: {"w": torch.tensor([0.0])}, lr=1.0, momentum=0.0, nesterov=False, round_timeout=5.0
    )

    with pytest.raises(RuntimeError):
        await service.Sync(make_request("a", 1, {"w": torch.tensor([1.0])}), FakeContext())


async def test_new_term_seeds_fresh_barrier_from_current_local_state():
    raft = FakeRaft(term=1, is_leader=True)
    local_state = {"w": torch.tensor([10.0])}

    async def get_quorum():
        return ["a"]

    service = LeaderGatedTrainerService(
        raft, get_quorum, lambda: local_state, lr=1.0, momentum=0.0, nesterov=False, round_timeout=5.0
    )

    resp = await service.Sync(make_request("a", 1, {"w": torch.tensor([1.0])}), FakeContext())
    state = state_from_pb(resp.global_state)
    assert torch.allclose(state["w"], torch.tensor([9.0]))  # 10 - 1*1

    # Term advances (a new leader was elected, possibly this same node
    # re-elected) and this node's own local state has moved on since.
    raft.term = 2
    local_state = {"w": torch.tensor([100.0])}

    resp2 = await service.Sync(make_request("a", 2, {"w": torch.tensor([5.0])}), FakeContext())
    state2 = state_from_pb(resp2.global_state)
    # Must be seeded from the *new* local_state (100), not continued
    # from the old barrier's result (9).
    assert torch.allclose(state2["w"], torch.tensor([95.0]))  # 100 - 1*5
