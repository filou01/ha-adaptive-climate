"""Joint ordinary moves must escape parallel clusters without changing grants."""

from dataclasses import replace

import pytest

from test_pwm_load_balancing import Simulation
from custom_components.adaptive_climate.managers.pwm_load_balancing_optimizer import ZoneRequest, plan
from custom_components.adaptive_climate.managers.pwm_runtime_planner import (
    RuntimeWindow as W,
    measure_windows,
    repair_windows,
)


@pytest.mark.parametrize("overlap", [120, 240])
@pytest.mark.parametrize("reverse", [False, True])
def test_joint_moves_escape_parallel_cluster_with_fixed_forecast(overlap, reverse):
    windows = [
        W("large", 4, 683 - overlap, 740, 0, 3600, True),
        W("small_b", 1, 0, 600, 0, 3600, True),
        W("small_c", 1, 3, 680, 3, 3, False, True),
    ]
    if reverse:
        windows.reverse()
    fixed = next(w for w in windows if w.entity_id == "small_c")
    before = measure_windows(windows, "large", overlap)
    result = repair_windows(windows, "large", overlap, {w.entity_id: w.start for w in windows})
    after = measure_windows(result, "large", overlap)
    by_id = {w.entity_id: w for w in result}
    assert after[:3] == before[:3] == (1, 0, overlap)
    assert after[3] == 5 * overlap
    assert after < before
    assert by_id["small_b"].start == fixed.end - overlap
    assert by_id["large"].start == by_id["small_b"].end - overlap
    assert by_id["small_c"] == fixed
    for old, new in zip(windows, result):
        assert old.duration == new.duration
        assert old.earliest <= new.start <= old.latest
    assert repair_windows(windows, "large", overlap, {}) == result


@pytest.mark.parametrize("fixed_kind", ["active", "priority", "forecast"])
def test_joint_repair_never_moves_a_committed_start(fixed_kind):
    windows = [
        W("large", 4, 563, 740, 0, 3600, True),
        W("small_b", 1, 0, 600, 0, 3600, True),
        W("small_c", 1, 3, 680, 3, 3, False, fixed_kind == "forecast"),
    ]
    result = repair_windows(windows, "large", 120, {})
    assert result[2] == windows[2]
    assert measure_windows(result, "large", 120) <= measure_windows(windows, "large", 120)


def test_joint_repair_respects_tight_latest_start_and_never_adds_a_pulse():
    windows = [
        W("large", 4, 563, 740, 563, 563),
        W("small_b", 1, 0, 600, 0, 100, True),
        W("small_c", 1, 3, 680, 3, 3, False, True),
    ]
    result = repair_windows(windows, "large", 120, {})
    assert len(result) == len(windows)
    assert result[0] == windows[0] and result[2] == windows[2]
    assert 0 <= result[1].start <= 100
    assert measure_windows(result, "large", 120) <= measure_windows(windows, "large", 120)


def test_zero_target_and_short_pulses_keep_valid_finite_windows():
    windows = [W("a", 4, 1, 10, 0, 100, True), W("b", 1, 0, 2, 0, 100, True), W("c", 1, 1, 3, 1, 1)]
    for overlap in (0, 120):
        result = repair_windows(windows, "a", overlap, {})
        assert measure_windows(result, "a", overlap) <= measure_windows(windows, "a", overlap)
        assert all(replace(new, start=old.start) == old for old, new in zip(windows, result))


@pytest.mark.parametrize("overlap", [120, 240])
def test_manager_uses_joint_chain_without_authorizing_forecast(overlap):
    sim = Simulation((740, 600, 680))
    group = sim.manager
    group._origin = -3600
    group.overlap = overlap
    entities = [z.entity_id for z in sim.zones]
    large, small, forecast = [group._zones[e] for e in entities]
    for ledger, duration in ((large, 740), (small, 600)):
        ledger.credit = ledger.allocation = duration
        ledger.next_budget_at = 3600
    forecast.credit, forecast.allocation = 0, 680
    forecast.next_budget_at, forecast.last_start_epoch = 3, 0
    phases = dict(zip(entities, (683 - overlap, 0, 3)))
    group.schedule = replace(
        plan([ZoneRequest(e, d, group.members[e]) for e, d in zip(entities, (740, 600, 680))], 3600, overlap),
        phases=phases,
    )
    group._runtime_starts = phases
    group._plan_executable(0, 0)
    assert group._runtime_starts[entities[1]] == 683 - overlap
    assert group._runtime_starts[entities[0]] == 1283 - 2 * overlap
    assert entities[2] not in group._runtime_starts
    assert group._runtime_projected_starts == 1
    assert not any(z.transitions for z in sim.zones)
