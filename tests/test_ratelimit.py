import pytest

from app.utils.ratelimit import ProviderThrottle


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_reserve_waits_once_burst_is_spent() -> None:
    clock = FakeClock()
    throttle = ProviderThrottle("test", rate_per_minute=60, burst=2, clock=clock)

    assert throttle.reserve() == 0
    assert throttle.reserve() == 0
    assert throttle.reserve() == pytest.approx(1.0)
    clock.now = 5
    assert throttle.reserve() == 0


def test_pause_overrides_bucket_and_never_shortens() -> None:
    clock = FakeClock()
    throttle = ProviderThrottle("test", rate_per_minute=600, clock=clock)

    throttle.pause(30)
    throttle.pause(10)

    assert throttle.paused
    assert throttle.reserve() == pytest.approx(30)
    clock.now = 31
    assert not throttle.paused
    assert throttle.reserve() == 0
