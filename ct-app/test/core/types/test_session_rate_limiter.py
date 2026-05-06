from core.types.session_rate_limiter import SessionRateLimiter


def test_rate_limiter_blocks_until_backoff_expires(mocker):
    relayer = "peer_1"
    limiter = SessionRateLimiter(base_delay=1.0, max_delay=10.0)

    monotonic = mocker.patch("core.types.session_rate_limiter.time.monotonic")
    monotonic.return_value = 10.0
    limiter.record_attempt(relayer)
    limiter.record_failure(relayer)

    monotonic.return_value = 11.0
    can_attempt, wait_time = limiter.can_attempt(relayer)

    assert not can_attempt
    assert wait_time == 1.0

    monotonic.return_value = 12.0
    can_attempt, wait_time = limiter.can_attempt(relayer)

    assert can_attempt
    assert wait_time is None


def test_rate_limiter_record_success_clears_tracking(mocker):
    relayer = "peer_2"
    limiter = SessionRateLimiter(base_delay=1.0, max_delay=10.0)

    mocker.patch("core.types.session_rate_limiter.time.monotonic", return_value=20.0)
    limiter.record_attempt(relayer)
    limiter.record_failure(relayer)

    limiter.record_success(relayer)

    assert limiter._failure_count == {}
    assert limiter._last_attempt == {}
    assert limiter.can_attempt(relayer) == (True, None)


def test_rate_limiter_get_stats_and_reset(mocker):
    relayer = "peer_3"
    limiter = SessionRateLimiter(base_delay=2.0, max_delay=10.0)

    monotonic = mocker.patch("core.types.session_rate_limiter.time.monotonic")
    monotonic.return_value = 100.0
    limiter.record_attempt(relayer)
    limiter.record_failure(relayer)
    limiter.record_failure(relayer)

    monotonic.return_value = 103.0
    stats = limiter.get_stats(relayer)

    assert stats["failures"] == 2
    assert stats["last_attempt_age_seconds"] == 3.0
    assert not stats["can_attempt"]
    assert stats["wait_time_seconds"] == 5.0

    limiter.reset(relayer)
    assert limiter.get_stats(relayer)["failures"] == 0
    assert limiter.get_stats(relayer)["can_attempt"]
