import pytest

from vaio_center.fan_policy import AUTO, LIMIT_C, QUIET_PCT, FanPolicy, aggressive_pct


def test_aggressive_curve():
    assert aggressive_pct(30) == 40
    assert aggressive_pct(45) == 40
    assert aggressive_pct(56.5) == 70
    assert aggressive_pct(68) == 100
    assert aggressive_pct(95) == 100
    assert all(aggressive_pct(t) % 5 == 0 for t in range(30, 100))


def test_normal_is_auto():
    assert FanPolicy("normal").target(50) == AUTO


def test_quiet_hysteresis():
    policy = FanPolicy("quiet")
    assert policy.target(50) == QUIET_PCT
    assert policy.target(60) == AUTO
    assert policy.target(57) == AUTO
    assert policy.target(55) == QUIET_PCT


def test_manual_is_clamped_and_max_is_100():
    assert FanPolicy("manual", 10).target(50) == 30
    assert FanPolicy("manual", 70).target(50) == 70
    assert FanPolicy("max").target(50) == 100


def test_manual_and_max_latch_to_auto_when_hot_until_mode_set_again():
    policy = FanPolicy("max")
    assert policy.target(LIMIT_C) == AUTO
    assert policy.forced
    assert policy.target(50) == AUTO
    policy.set_mode("max")
    assert not policy.forced
    assert policy.target(50) == 100


def test_one_missed_read_keeps_last_target_two_fail_closed():
    policy = FanPolicy("aggressive")
    assert policy.target(70) == 100
    assert policy.target(None) == 100
    assert policy.target(None) == AUTO
    assert policy.target(70) == 100


def test_aggressive_hysteresis_delays_step_down():
    """R5: only step down when temp+2 also computes below the current step."""
    policy = FanPolicy("aggressive")
    assert policy.target(56.5) == 70
    assert policy.target(55.0) == 70  # raw pct is 65, but +2 still rounds to 70: hold
    assert policy.target(52) == 60  # +2 now also drops below 70: step down


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        FanPolicy("turbo")
