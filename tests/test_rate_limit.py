from src.hosted.rate_limit import OrgRateLimiter


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_bucket_exhausts_at_capacity():
    clock = _Clock()
    limiter = OrgRateLimiter(per_minute=5, now=clock)
    assert all(limiter.allow("org-1") for _ in range(5))
    assert not limiter.allow("org-1")


def test_refills_over_time():
    clock = _Clock()
    limiter = OrgRateLimiter(per_minute=60, now=clock)  # 1 token/second
    for _ in range(60):
        assert limiter.allow("org-1")
    assert not limiter.allow("org-1")
    clock.t += 2.5
    assert limiter.allow("org-1")
    assert limiter.allow("org-1")
    assert not limiter.allow("org-1")


def test_orgs_isolated():
    clock = _Clock()
    limiter = OrgRateLimiter(per_minute=2, now=clock)
    assert limiter.allow("org-a")
    assert limiter.allow("org-a")
    assert not limiter.allow("org-a")
    assert limiter.allow("org-b")  # unaffected by org-a's exhaustion
