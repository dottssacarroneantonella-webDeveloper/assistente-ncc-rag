from app.core.ratelimit import SlidingWindowLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_events_and_recovers() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(3, 60, clock=clock)
    for _ in range(3):
        assert not limiter.is_blocked("ip")
        limiter.hit("ip")
    assert limiter.is_blocked("ip")
    assert 0 < limiter.retry_after("ip") <= 60
    assert not limiter.is_blocked("altro-ip")
    clock.now = 60
    assert not limiter.is_blocked("ip")
    assert limiter.retry_after("ip") == 0


def test_reset() -> None:
    limiter = SlidingWindowLimiter(1, 60)
    limiter.hit("ip")
    assert limiter.is_blocked("ip")
    limiter.reset("ip")
    assert not limiter.is_blocked("ip")
