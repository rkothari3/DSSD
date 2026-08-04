"""The DiLoCo outer step: aggregate what each worker learned locally
into a new shared global model.

Per the original DiLoCo paper (Douillard et al., "DiLoCo: Distributed
Low-Communication Training of Language Models," arXiv:2311.08105), each
worker runs many local inner-optimizer (AdamW) steps, then the group
synchronizes by averaging "pseudo-gradients" - how far each worker moved
from the shared starting point - and applying them to the global model
with an outer optimizer (SGD with Nesterov momentum).
"""

from __future__ import annotations

import torch

StateDict = dict[str, torch.Tensor]


def pseudo_gradient(global_state: StateDict, worker_state: StateDict) -> StateDict:
    """How far a worker's local training moved its parameters away from
    the shared global state, treated as a gradient for the outer
    optimizer."""
    return {k: global_state[k] - worker_state[k] for k in global_state}


def average_pseudo_gradients(pseudo_grads: list[StateDict]) -> StateDict:
    if not pseudo_grads:
        raise ValueError("diloco: need at least one worker's pseudo-gradient to average")
    keys = pseudo_grads[0].keys()
    return {k: torch.stack([g[k] for g in pseudo_grads]).mean(dim=0) for k in keys}


class OuterOptimizer:
    """Wraps torch.optim.SGD to apply the averaged pseudo-gradient to the
    global model state, since the global params during outer-step
    aggregation aren't leaf tensors in any live autograd graph."""

    def __init__(self, global_state: StateDict, lr: float = 0.7, momentum: float = 0.9, nesterov: bool = True) -> None:
        self._params = {k: v.clone().detach().requires_grad_(True) for k, v in global_state.items()}
        self._optim = torch.optim.SGD(self._params.values(), lr=lr, momentum=momentum, nesterov=nesterov)

    def step(self, avg_pseudo_grad: StateDict) -> StateDict:
        self._optim.zero_grad()
        for k, p in self._params.items():
            p.grad = avg_pseudo_grad[k].clone()
        self._optim.step()
        return {k: p.detach().clone() for k, p in self._params.items()}
