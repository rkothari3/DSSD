import csv

import pytest

from dssd.diloco.metrics import MetricsRecorder, average_loss


def test_average_loss_ignores_unreachable_workers():
    assert average_loss({"a": 1.0, "b": 3.0, "c": None}) == pytest.approx(2.0)


def test_average_loss_is_none_when_nothing_reachable():
    assert average_loss({"a": None, "b": None}) is None


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.now += seconds


async def test_recorder_polls_at_interval_until_duration_elapses():
    clock = FakeClock()
    losses = iter([{"a": 2.0}, {"a": 1.5}, {"a": 1.0}])

    async def poll_fn():
        return next(losses)

    recorder = MetricsRecorder(poll_fn=poll_fn, interval=1.0, now=clock.time, sleep=clock.sleep)
    await recorder.run(duration=2.5)

    assert [row.elapsed for row in recorder.rows] == [0.0, 1.0, 2.0]
    assert [row.avg_loss for row in recorder.rows] == [2.0, 1.5, 1.0]


async def test_recorder_writes_csv(tmp_path):
    clock = FakeClock()

    async def poll_fn():
        return {"a": 1.0}

    recorder = MetricsRecorder(poll_fn=poll_fn, interval=1.0, now=clock.time, sleep=clock.sleep)
    await recorder.run(duration=0.5)

    out = tmp_path / "run.csv"
    recorder.write_csv(out)

    with open(out, newline="") as f:  # noqa: ASYNC230 - trivial read of a just-written test fixture
        rows = list(csv.DictReader(f))
    assert rows == [{"elapsed": "0.0", "avg_loss": "1.0"}]
