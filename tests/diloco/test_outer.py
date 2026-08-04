import torch

from dssd.diloco.outer import OuterOptimizer, average_pseudo_gradients, pseudo_gradient


def test_pseudo_gradient_is_global_minus_worker():
    global_state = {"w": torch.tensor([1.0, 2.0])}
    worker_state = {"w": torch.tensor([0.5, 1.5])}

    grad = pseudo_gradient(global_state, worker_state)

    assert torch.allclose(grad["w"], torch.tensor([0.5, 0.5]))


def test_average_pseudo_gradients_across_workers():
    grads = [
        {"w": torch.tensor([1.0, 0.0])},
        {"w": torch.tensor([3.0, 2.0])},
    ]

    avg = average_pseudo_gradients(grads)

    assert torch.allclose(avg["w"], torch.tensor([2.0, 1.0]))


def test_average_pseudo_gradients_requires_at_least_one():
    try:
        average_pseudo_gradients([])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_outer_step_matches_plain_sgd_without_momentum():
    global_state = {"w": torch.tensor([1.0, 2.0])}
    outer = OuterOptimizer(global_state, lr=0.5, momentum=0.0, nesterov=False)

    pseudo_grad = {"w": torch.tensor([0.2, -0.4])}
    new_state = outer.step(pseudo_grad)

    expected = torch.tensor([1.0 - 0.5 * 0.2, 2.0 - 0.5 * -0.4])
    assert torch.allclose(new_state["w"], expected)


def test_outer_step_with_momentum_accumulates_across_steps():
    global_state = {"w": torch.tensor([0.0])}
    outer = OuterOptimizer(global_state, lr=1.0, momentum=0.9, nesterov=False)

    # Constant pseudo-gradient across steps: momentum should make later
    # steps move further than the first.
    first = outer.step({"w": torch.tensor([1.0])})
    second = outer.step({"w": torch.tensor([1.0])})

    first_delta = global_state["w"] - first["w"]
    second_delta = first["w"] - second["w"]
    assert second_delta.item() > first_delta.item()
