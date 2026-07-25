"""The adaptive orbit policy (plan_orbit). Pure logic, no DB, network, or keys."""

from app.tick import ORBIT_CALM_PASSES, plan_orbit


def test_change_tightens_to_half_base():
    cadence, streak, reason = plan_orbit(base=60, current=60, stable_passes=2, changed=True)
    assert cadence == 30
    assert streak == 0
    assert "tightened" in reason


def test_change_never_goes_below_global_floor():
    cadence, _, _ = plan_orbit(base=20, current=20, stable_passes=0, changed=True)
    assert cadence == 15


def test_change_at_floor_is_a_no_op_but_resets_streak():
    cadence, streak, reason = plan_orbit(base=60, current=30, stable_passes=2, changed=True)
    assert cadence == 30
    assert streak == 0
    assert reason is None


def test_calm_passes_accumulate_before_relaxing():
    streak = 0
    for i in range(ORBIT_CALM_PASSES - 1):
        cadence, streak, reason = plan_orbit(60, 60, streak, changed=False)
        assert cadence == 60
        assert reason is None
        assert streak == i + 1


def test_relaxes_after_calm_streak_and_resets():
    cadence, streak, reason = plan_orbit(
        base=60, current=60, stable_passes=ORBIT_CALM_PASSES - 1, changed=False
    )
    assert cadence == 90  # one step: half again slower
    assert streak == 0
    assert "relaxed" in reason


def test_relaxation_capped_at_four_times_base():
    cadence, _, _ = plan_orbit(
        base=60, current=200, stable_passes=ORBIT_CALM_PASSES - 1, changed=False
    )
    assert cadence == 240
    cadence, streak, reason = plan_orbit(
        base=60, current=240, stable_passes=ORBIT_CALM_PASSES - 1, changed=False
    )
    assert cadence == 240  # at the ceiling: no change, streak still resets
    assert streak == 0
    assert reason is None


def test_relaxation_never_exceeds_global_ceiling():
    cadence, _, _ = plan_orbit(
        base=1440, current=1440, stable_passes=ORBIT_CALM_PASSES - 1, changed=False
    )
    assert cadence == 1440


def test_tiny_cadence_still_makes_progress():
    # 15 * 3 // 2 = 22: the +1 guard is not needed here, but 1-minute steps
    # would stall without it. Assert relaxation moves at the minimum cadence.
    cadence, _, reason = plan_orbit(
        base=15, current=15, stable_passes=ORBIT_CALM_PASSES - 1, changed=False
    )
    assert cadence > 15
    assert reason is not None


def test_round_trip_tighten_then_recover():
    # A volatile page tightens 120 -> 60, then three calm rounds start walking
    # it back up toward the ordered cadence and beyond, capped at 480.
    cadence, streak, _ = plan_orbit(120, 120, 0, changed=True)
    assert cadence == 60
    for _ in range(20):  # plenty of calm passes
        cadence, streak, _ = plan_orbit(120, cadence, streak, changed=False)
    assert cadence == 480  # settled at base * 4
